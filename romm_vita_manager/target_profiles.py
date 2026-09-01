from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeCapability:
    key: str
    name: str
    runtime_type: str
    retroachievements: str = "none"
    notes: str = ""


@dataclass(frozen=True)
class TargetProfile:
    key: str
    device_key: str
    name: str
    transport_types: tuple[str, ...]
    root_kind: str
    runtimes: tuple[RuntimeCapability, ...] = field(default_factory=tuple)
    notes: str = ""


TARGET_PROFILES = (
    TargetProfile(
        key="vita-ux0",
        device_key="vita",
        name="Vita ux0",
        transport_types=("mounted", "usb"),
        root_kind="vita_ux0",
        runtimes=(
            RuntimeCapability("retroflow", "RetroFlow", "frontend"),
            RuntimeCapability("adrenaline", "Adrenaline", "runtime"),
            RuntimeCapability("retroarch", "RetroArch", "emulator"),
        ),
    ),
    TargetProfile(
        key="3ds-sd",
        device_key="3ds",
        name="3DS SD Card",
        transport_types=("mounted", "ftp"),
        root_kind="3ds_sd",
        runtimes=(
            RuntimeCapability("open-agb-firm", "open_agb_firm", "native", notes="Native GBA hardware route."),
            RuntimeCapability("retroarch", "RetroArch", "emulator"),
            RuntimeCapability("twilight", "TWiLight Menu++", "frontend"),
            RuntimeCapability("red-viper", "Red Viper", "emulator", retroachievements="experimental"),
            RuntimeCapability("daedalusx64", "DaedalusX64", "emulator"),
        ),
    ),
    TargetProfile(
        key="ds-flashcard",
        device_key="3ds",
        name="DS / Slot-1 Flashcard",
        transport_types=("mounted",),
        root_kind="ds_flashcard",
        runtimes=(
            RuntimeCapability("twilight", "TWiLight Menu++", "frontend"),
            RuntimeCapability("nds-bootstrap", "nds-bootstrap", "loader", notes="B4DS/native DS loader depending on target."),
            RuntimeCapability("flashcard-kernel", "Flashcard kernel", "loader"),
            RuntimeCapability("gbarunner2", "GBARunner2", "runtime"),
        ),
        notes="Exact flashcard hardware model should remain unknown unless hardware-specific evidence is available.",
    ),
)


def target_profiles_for_device(device_key: str) -> tuple[TargetProfile, ...]:
    return tuple(profile for profile in TARGET_PROFILES if profile.device_key == device_key)
