from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib import error, request
from urllib.parse import quote_plus, urljoin

HSHOP_BASE = "https://hshop.erista.me"
_SEARCH_URL = HSHOP_BASE + "/search/results?count=100&lgy=false&q={query}&qt=Text"
_PLATFORM_LABELS = {
    "gb": "game boy",
    "gbc": "game boy color",
    "gba": "game boy advance",
    "nes": "nes",
    "famicom": "nes",
    "fds": "nes",
    "snes": "super nintendo",
    "gamegear": "game gear",
}


@dataclass(frozen=True)
class HShopVcRelease:
    title: str
    url: str
    platform: str
    region: str
    title_id: str
    product_code: str
    content_type: str


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._parts: list[str] = []
        self.entries: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if isinstance(href, str) and re.fullmatch(r"/t/\d+", href):
            self._href = href
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            text = " ".join(" ".join(self._parts).split())
            self.entries.append((self._href, text))
            self._href = None
            self._parts = []


def _normalise_title(value: str) -> str:
    # Remove presentation-only marks before compatibility decomposition.
    # NFKD expands ™ to "TM", which would otherwise make an exact title like
    # "PAC-MAN™" compare as "pac mantm" rather than "pac man".
    value = value.replace("™", "").replace("®", "")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _title_score(query: str, candidate: str) -> int:
    q = _normalise_title(query)
    c = _normalise_title(candidate)
    if not q or not c:
        return 0
    if q == c:
        return 100
    if q in c or c in q:
        return 85
    q_words = set(q.split())
    c_words = set(c.split())
    if not q_words:
        return 0
    overlap = len(q_words & c_words) / len(q_words)
    return int(overlap * 70)


def _parse_entry(href: str, text: str) -> HShopVcRelease | None:
    lower = text.casefold()
    if "content in virtual-console" not in lower:
        return None

    split = re.split(r"\s+content in virtual-console\s+➞\s+", text, maxsplit=1, flags=re.I)
    title = split[0].strip() if split else text.strip()
    tail = split[1] if len(split) == 2 else text

    platform_match = re.search(r"Virtual Console:\s*([^0-9]+?)\s+\d+\s+ID\b", tail, re.I)
    platform = platform_match.group(1).strip() if platform_match else "Virtual Console"
    region = tail.split("Virtual Console:", 1)[0].strip() if "Virtual Console:" in tail else ""
    title_id_match = re.search(r"\b([0-9A-F]{16})\s+Title ID\b", text, re.I)
    product_match = re.search(r"\b(CTR-[A-Z0-9-]+)\s+Product Code\b", text, re.I)
    content_match = re.search(r"\b(Legit|Pirate Legit|Standard)\s+Content Type\b", text, re.I)

    return HShopVcRelease(
        title=title,
        url=urljoin(HSHOP_BASE, href),
        platform=platform,
        region=region,
        title_id=title_id_match.group(1).upper() if title_id_match else "",
        product_code=product_match.group(1) if product_match else "",
        content_type=content_match.group(1) if content_match else "",
    )


def find_official_vc_release(
    title: str,
    platform_slug: str,
    *,
    timeout: float = 8.0,
    opener=None,
) -> HShopVcRelease | None:
    """Find a likely official 3DS Virtual Console release in hShop metadata.

    hShop is used only as a public catalogue. This function does not request or
    download CIA content.
    """
    expected = _PLATFORM_LABELS.get(platform_slug.casefold())
    if expected is None:
        return None

    req = request.Request(
        _SEARCH_URL.format(query=quote_plus(title)),
        headers={"User-Agent": "RommHeld/1.0", "Accept": "text/html"},
    )
    client = opener or request.build_opener()
    try:
        with client.open(req, timeout=timeout) as response:
            html = response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
    except (error.URLError, TimeoutError, OSError):
        return None

    parser = _SearchParser()
    parser.feed(html)
    candidates: list[tuple[int, HShopVcRelease]] = []
    for href, text in parser.entries:
        release = _parse_entry(href, text)
        if release is None:
            continue
        platform_text = _normalise_title(release.platform)
        if expected not in platform_text:
            continue
        score = _title_score(title, release.title)
        if score >= 70:
            candidates.append((score, release))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], bool(item[1].title_id)), reverse=True)
    return candidates[0][1]
