from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping

from .vita_health import (
    HEALTHY,
    MISCONFIGURED,
    MISSING,
    OUTDATED,
    UNKNOWN,
    VitaComponentHealth,
)


_KUBRIDGE_MINIMUM = (0, 3, 1)


@dataclass(frozen=True)
class VitaHardwareEvidence:
    """Sanitized operational evidence gathered during real-device validation.

    ``verified_components`` means the named component/runtime condition was
    actually exercised successfully on the Vita, not merely observed in a file
    listing. ``trusted_versions`` is reserved for versions obtained from a source
    that really identifies the installed binary/package. Filenames alone are not
    a trusted version source.
    """

    verified_components: frozenset[str] = frozenset()
    trusted_versions: Mapping[str, str] = field(default_factory=dict, compare=False)

    @classmethod
    def from_observations(
        cls,
        *,
        verified_components: Iterable[str] = (),
        trusted_versions: Mapping[str, str] | None = None,
    ) -> "VitaHardwareEvidence":
        return cls(
            frozenset(value.strip().casefold() for value in verified_components),
            {
                key.strip().casefold(): str(value).strip()
                for key, value in (trusted_versions or {}).items()
            },
        )


def _version_tuple(value: str) -> tuple[int, ...] | None:
    match = re.search(r"(?<!\d)(\d+)(?:\.(\d+))?(?:\.(\d+))?", value)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _apply_kubridge_version(
    component: VitaComponentHealth,
    version: str | None,
) -> VitaComponentHealth:
    if not version or component.state in {MISCONFIGURED, MISSING, UNKNOWN}:
        return component
    parsed = _version_tuple(version)
    if parsed is None:
        return component
    normalized = (parsed + (0, 0, 0))[:3]
    if normalized < _KUBRIDGE_MINIMUM:
        return replace(
            component,
            state=OUTDATED,
            summary=(
                f"Trusted hardware/package evidence identifies kubridge {version}. "
                "DSVita requires kubridge 0.3.1 or later, so this dependency is outdated."
            ),
            evidence=component.evidence + (f"hardware:version:kubridge={version}",),
        )
    return replace(
        component,
        state=HEALTHY,
        summary=(
            f"kubridge is present in the active *KERNEL configuration and trusted evidence "
            f"identifies version {version}, satisfying the DSVita >= 0.3.1 requirement."
        ),
        evidence=component.evidence + (f"hardware:version:kubridge={version}",),
    )


def apply_vita_hardware_evidence(
    health: Mapping[str, VitaComponentHealth],
    hardware: VitaHardwareEvidence,
) -> dict[str, VitaComponentHealth]:
    """Overlay explicit real-device results on conservative filesystem health.

    A successful hardware observation is stronger than an incomplete desktop
    filesystem view, so a specifically verified component can become Healthy even
    when its installation lived outside the inspected volume. Version-sensitive
    classification is kept separate and is only applied when a trusted installed
    version was supplied.
    """

    result = dict(health)
    if "kubridge" in result:
        result["kubridge"] = _apply_kubridge_version(
            result["kubridge"],
            hardware.trusted_versions.get("kubridge"),
        )

    for key in hardware.verified_components:
        component = result.get(key)
        if component is None:
            continue
        version = hardware.trusted_versions.get(key)
        version_text = f" Version {version} was also recorded." if version else ""
        result[key] = replace(
            component,
            state=HEALTHY,
            summary=(
                "This component was exercised successfully on real Vita hardware during "
                f"validation.{version_text} Filesystem evidence remains diagnostic only."
            ),
            evidence=component.evidence + (f"hardware:verified:{key}",),
        )

    return result


__all__ = [
    "VitaHardwareEvidence",
    "apply_vita_hardware_evidence",
]
