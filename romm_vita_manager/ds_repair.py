from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ds_runtime import DsHealthReport, inspect_ds_runtime


@dataclass(frozen=True)
class DsRepairAction:
    key: str
    scope: str
    label: str
    description: str


SAFE_CONTENT_DIRECTORIES = ("roms/nds", "roms/nds/saves")


def plan_ds_repairs(report: DsHealthReport) -> tuple[DsRepairAction, ...]:
    """Return the safe/manual boundary without silently changing runtime files."""
    if report.profile.key == "3ds-hosted-twilight":
        return (
            DsRepairAction(
                "defer-3ds",
                "manual",
                "Use 3DS readiness",
                "This storage belongs to the 3DS workflow; DS repair intentionally performs no writes.",
            ),
        )

    actions: list[DsRepairAction] = []
    if report.check("rom-directories").state != "verified" or report.check("save-directories").state != "verified":
        actions.append(
            DsRepairAction(
                "create-content-directories",
                "safe",
                "Create DS content/save directories",
                "Create /roms/nds/ and /roms/nds/saves/ only. Existing files are left untouched.",
            )
        )

    for key, label in (
        ("twilight-menu", "Repair/update TWiLight Menu++"),
        ("nds-bootstrap", "Repair/update nds-bootstrap"),
        ("launcher", "Restore the environment launcher"),
    ):
        check = report.check(key)
        if check.state in {"missing", "needs_attention"}:
            actions.append(
                DsRepairAction(
                    f"guide-{key}",
                    "guided",
                    label,
                    "Use the maintained environment-specific TWiLight Menu++ release/update instructions. RommHeld does not copy isolated runtime or autoboot files from mixed releases.",
                )
            )

    if report.check("config").state == "needs_attention":
        actions.append(
            DsRepairAction(
                "repair-config",
                "guided",
                "Regenerate TWiLight settings safely",
                "Back up the malformed settings.ini before allowing the installed TWiLight Menu++ version to regenerate it. Do not reconstruct undocumented keys automatically.",
            )
        )

    if report.profile.key == "dsi-homebrew":
        actions.append(
            DsRepairAction(
                "confirm-dsi-boot",
                "manual",
                "Confirm DSi boot environment",
                "Verify Unlaunch/boot target on the console. NAND installation or boot-chain repair is intentionally outside automatic RommHeld repair.",
            )
        )
    elif report.profile.key == "ds-flashcart" and not report.check("flashcart-kernel").paths:
        actions.append(
            DsRepairAction(
                "confirm-flashcart",
                "manual",
                "Identify the flashcart",
                "Confirm the exact cart/revision before installing a cart-specific kernel or autoboot package.",
            )
        )
    return tuple(actions)


def create_ds_content_directories(root: Path, *, profile_hint: str | None = None) -> tuple[Path, ...]:
    """Apply the only default automatic DS repair: known content/save folders."""
    report = inspect_ds_runtime(root, profile_hint=profile_hint)
    if report.profile.key == "3ds-hosted-twilight":
        raise ValueError("3DS-hosted TWiLight storage is owned by the 3DS readiness workflow")

    created: list[Path] = []
    for relative in SAFE_CONTENT_DIRECTORIES:
        destination = report.root / relative
        if not destination.exists():
            destination.mkdir(parents=True, exist_ok=True)
            created.append(destination)
        elif not destination.is_dir():
            raise NotADirectoryError(f"Expected a directory but found a file: {destination}")
    return tuple(created)


__all__ = ["DsRepairAction", "SAFE_CONTENT_DIRECTORIES", "create_ds_content_directories", "plan_ds_repairs"]
