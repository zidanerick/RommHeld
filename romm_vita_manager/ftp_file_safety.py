from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemotePathRisk:
    level: str
    title: str
    message: str

    def __post_init__(self) -> None:
        if self.level not in {"normal", "caution", "critical"}:
            raise ValueError(f"Unknown remote path risk level: {self.level}")


_THREE_DS_CRITICAL = {
    "nintendo 3ds": "This is the console-managed encrypted title/save-data tree. Deleting or renaming files here can make installed titles or saves inaccessible.",
    "luma": "This contains Luma3DS configuration, payloads and support files. Changes can affect boot or homebrew behavior.",
    "gm9": "This contains GodMode9 support data and scripts. Delete only files you explicitly recognise.",
    "boot.firm": "This is commonly the Luma3DS boot payload. Removing or replacing it can prevent the console from booting normally.",
    "boot.3dsx": "This is commonly the Homebrew Launcher environment entry file. Removing it can break Homebrew Launcher access.",
}

_THREE_DS_CAUTION = {
    "3ds": "This is the main Homebrew Launcher application tree. Deleting entries can remove or break homebrew applications.",
    "_nds": "This contains TWiLight Menu++/nds-bootstrap and other DS-mode support data. Changes can break DS launch workflows.",
    "cias": "This commonly stores install packages. Deletion is usually recoverable but may remove the only local copy of a package.",
}

_VITA_CRITICAL = {
    "app": "This contains installed Vita applications. Deleting or renaming entries can break installed software.",
    "appmeta": "This contains application metadata used by the Vita shell. Changes can break bubbles or application metadata.",
    "license": "This contains licence data. Deleting entries can make legitimately installed content unusable.",
    "patch": "This contains application patch data. Changes can break updated applications.",
    "user": "This contains console-managed user data. Changes can affect saves and application state.",
    "tai": "This can contain taiHEN configuration/plugins on some setups. Incorrect changes may affect homebrew/plugin startup.",
}

_VITA_CAUTION = {
    "data": "Applications often keep configuration and user data here. Delete only files you recognise.",
    "pspemu": "This contains Adrenaline/PSP content and save data. Changes can remove games or saves.",
    "addcont": "This contains add-on content. Changes can break DLC/add-on installations.",
    "repatch": "This is commonly used by rePatch workflows. Changes can alter application overrides.",
}


def destructive_path_risk(console: str, path: str) -> RemotePathRisk:
    cleaned = path.strip().replace("\\", "/").strip("/")
    top = cleaned.split("/", 1)[0].casefold() if cleaned else ""
    normalized_console = console.strip().casefold()

    if normalized_console in {"3ds", "nintendo 3ds"}:
        if top in _THREE_DS_CRITICAL:
            return RemotePathRisk("critical", "Sensitive Nintendo 3DS path", _THREE_DS_CRITICAL[top])
        if top in _THREE_DS_CAUTION:
            return RemotePathRisk("caution", "Nintendo 3DS application data", _THREE_DS_CAUTION[top])
    elif normalized_console in {"vita", "ps vita", "playstation vita", "pstv", "playstation tv"}:
        if top in _VITA_CRITICAL:
            return RemotePathRisk("critical", "Sensitive Vita path", _VITA_CRITICAL[top])
        if top in _VITA_CAUTION:
            return RemotePathRisk("caution", "Vita application data", _VITA_CAUTION[top])

    return RemotePathRisk(
        "normal",
        "Delete remote item",
        "This operation permanently removes the selected remote item.",
    )


__all__ = ["RemotePathRisk", "destructive_path_risk"]
