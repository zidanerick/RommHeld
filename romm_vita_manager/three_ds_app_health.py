from __future__ import annotations

from dataclasses import dataclass

from .three_ds_apps import ThreeDSAppStatus


@dataclass(frozen=True)
class ThreeDSAppHealth:
    state: str
    label: str
    summary: str
    steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in {"verified", "not_verified", "needs_attention", "missing"}:
            raise ValueError(f"Unknown 3DS app health state: {self.state}")

    @property
    def troubleshooting_text(self) -> str:
        if not self.steps:
            return self.summary
        numbered = "\n".join(f"{index}. {step}" for index, step in enumerate(self.steps, 1))
        return f"{self.summary}\n\nIf it is installed but not working:\n{numbered}"


def _detected_not_verified(
    status: ThreeDSAppStatus,
    summary: str,
    *steps: str,
) -> ThreeDSAppHealth:
    return ThreeDSAppHealth("not_verified", "Present · Launch not verified", summary, tuple(steps))


def assess_three_ds_app_health(
    status: ThreeDSAppStatus,
    *,
    ftp_error: str | None = None,
) -> ThreeDSAppHealth:
    """Describe operational confidence separately from installation evidence.

    ``ThreeDSAppStatus.state`` carries source-independent evidence semantics.
    This helper adds user-facing diagnosis and the safest repair boundary. File
    presence never becomes a launch-success claim; only a successful live ftpd
    connection is currently operationally verified by RommHeld itself.
    """

    app = status.definition
    key = app.key

    if key == "ftpd":
        if status.detected and status.source == "ftp_live" and not ftp_error:
            return ThreeDSAppHealth(
                "verified",
                "Working · Live connection verified",
                "RommHeld connected to the running ftpd service and could inspect the console filesystem.",
                (
                    "If later connections fail, reopen ftpd and leave it running while RommHeld is connected.",
                    "Use the IP address and port currently shown by ftpd because DHCP can change the console address.",
                ),
            )
        if ftp_error:
            return ThreeDSAppHealth(
                "needs_attention",
                "Needs attention · Service unreachable",
                f"ftpd installation evidence exists, but the live service check failed: {ftp_error}",
                (
                    "Launch ftpd on the 3DS and leave it open on its server screen.",
                    "Confirm RommHeld uses the IP address and port currently shown by ftpd and that both devices are on the same LAN.",
                    "If ftpd itself will not launch, update or reinstall it with Universal-Updater, or prepare RommHeld's verified Homebrew Launcher 3DSX build on a mounted SD card as a diagnostic fallback.",
                    "Refresh readiness and verify that the state changes to a live FTP connection before relying on wireless transfers.",
                ),
            )
        if status.detected:
            return _detected_not_verified(
                status,
                "ftpd is present, but RommHeld has not confirmed that the FTP server is currently running.",
                "Launch ftpd on the 3DS and leave it open on the server screen.",
                "Enter the displayed IP address and port in RommHeld, then refresh readiness to perform a live service check.",
                "If the application will not launch, update or reinstall it with Universal-Updater or use RommHeld's verified 3DSX preparation path.",
            )

    if status.state == "partial":
        if key == "open-agb-firm":
            missing = ", ".join(status.missing_health_markers) or "the bundled support files"
            return ThreeDSAppHealth(
                "needs_attention",
                "Partial installation · Support files missing",
                (
                    "The open_agb_firm payload is present, but the upstream release layout is incomplete. "
                    f"Missing expected support data: {missing}."
                ),
                (
                    "Download the current official open_agb_firm release from upstream.",
                    "When repairing manually, copy both open_agb_firm.firm to /luma/payloads and the release's 3ds folder to the SD root, merging folders rather than deleting unrelated files.",
                    "Do not create config.ini by hand. Launch open_agb_firm once so the installed version can generate a version-matched configuration file.",
                    "Refresh RommHeld readiness. RommHeld will not automatically reconstruct this multi-file runtime while the maintained/manual boundary remains safer.",
                ),
            )
        return ThreeDSAppHealth(
            "needs_attention",
            "Partial installation",
            f"RommHeld found only part of the expected {app.name} filesystem evidence.",
            (
                "Use the application's maintained install/update path rather than deleting unknown files or copying isolated pieces.",
                "Launch the repaired application once on the console, then refresh RommHeld readiness.",
            ),
        )

    if status.state == "unknown":
        return ThreeDSAppHealth(
            "missing",
            "Unknown · Console confirmation required",
            (
                f"RommHeld has no reliable evidence from the checked sources that {app.name} is available, but an installed CIA title may still exist on the console."
            ),
            (
                "Check the console directly for the application before reinstalling anything.",
                "If it is absent or broken, use the preparation/updater/upstream action offered by readiness for this component.",
                "Refresh readiness after installation or repair.",
            ),
        )

    if key == "fbi" and status.detected:
        return _detected_not_verified(
            status,
            "FBI is present, but filesystem evidence cannot prove that the application launches or that Remote Install is usable.",
            "Launch FBI from the HOME Menu or Homebrew Launcher entry indicated by the detected evidence.",
            "Confirm FBI opens normally and that its Remote Install workflow is available before relying on RommHeld direct installation.",
            "If FBI will not launch, update or reinstall it from its maintained upstream release or Universal-Updater; RommHeld can also prepare the verified Homebrew Launcher 3DSX build on a mounted SD card.",
            "After repair, retry a small lawful CIA through RommHeld's FBI Remote Install workflow and confirm completion on the console.",
        )

    if key == "universal-updater" and status.detected:
        return _detected_not_verified(
            status,
            "Universal-Updater is present, but RommHeld cannot remotely prove that its catalogue or install actions work.",
            "Launch Universal-Updater on the console and refresh its catalogue.",
            "If it crashes or cannot update, replace it with RommHeld's verified Homebrew Launcher bootstrap or the current maintained upstream release.",
            "Once it launches normally, use its maintained recipes for complex applications instead of manually reconstructing their file layouts.",
        )

    if key == "red-viper" and status.detected:
        return _detected_not_verified(
            status,
            "Red Viper is present, but RommHeld has not verified an actual Virtual Boy game launch.",
            "Launch Red Viper directly and test a known-good ROM from the SD card.",
            "If it fails to start, update or reinstall Red Viper through Universal-Updater or the maintained upstream release.",
            "If the application launches but games freeze or audio fails, confirm the console-generated DSP firmware prerequisite and retry before changing ROM paths.",
        )

    if key == "checkpoint" and status.detected:
        return _detected_not_verified(
            status,
            "Checkpoint is present, but RommHeld cannot verify that it launches or can enumerate save data.",
            "Launch Checkpoint on the console and allow it to enumerate installed titles.",
            "If it will not launch, update or reinstall it through Universal-Updater or its maintained upstream release; RommHeld can prepare the verified 3DSX build on a mounted SD card.",
            "Do not treat a staged Checkpoint 3DSX file as proof that the CIA title is installed.",
        )

    if key == "daedalusx64" and status.detected:
        return _detected_not_verified(
            status,
            "DaedalusX64 is present, but RommHeld has not verified an N64 game launch.",
            "Launch DaedalusX64 and test a known-compatible ROM before changing RommHeld destination mappings.",
            "If the frontend fails to launch, update or reinstall it using Universal-Updater or the maintained upstream package.",
            "If game launch freezes, confirm the console-generated DSP firmware recommended by the 3DS build and check the emulator's own compatibility guidance.",
        )

    if key == "open-agb-firm" and status.detected:
        return _detected_not_verified(
            status,
            "The open_agb_firm payload and required bundled support data are present, but RommHeld cannot prove that the Luma payload chainloader can launch them.",
            "Power on while holding START and confirm open_agb_firm appears in the Luma3DS chainloader.",
            "If the payload is missing or fails to start, replace the full runtime from the current official upstream release rather than copying only the .firm file.",
            "If the payload starts but a game fails, validate the ROM and open_agb_firm configuration separately from the installation files.",
        )

    if key == "twilight":
        if status.detected:
            return _detected_not_verified(
                status,
                "TWiLight Menu++ launch evidence is present, but RommHeld cannot verify that nds-bootstrap launches a game successfully.",
                "Launch TWiLight Menu++ on the console and test a known-good DS title.",
                "Use Universal-Updater to repair/update the maintained TWiLight Menu++ and nds-bootstrap installation if the frontend or game launch fails.",
                "Keep the frontend assets and nds-bootstrap versions aligned instead of replacing only one folder.",
            )
        if status.marker:
            return ThreeDSAppHealth(
                "needs_attention",
                "Needs attention · Runtime assets only · Launcher not verified",
                "TWiLight Menu++/nds-bootstrap assets are present, but a launchable frontend is not confirmed.",
                (
                    "Launch the console and check whether TWiLight Menu++ has a HOME Menu or Homebrew Launcher entry.",
                    "If it is missing or broken, use Universal-Updater to repair the full maintained TWiLight Menu++ installation rather than copying only individual runtime folders.",
                    "Refresh RommHeld readiness after the repair.",
                ),
            )

    if key == "retroarch":
        if status.detected:
            return _detected_not_verified(
                status,
                "RetroArch is present, but RommHeld has not verified the selected frontend/core/firmware route on-console.",
                "Launch RetroArch and confirm the intended core is installed and visible.",
                "Update or reinstall the frontend/core bundle through the maintained package source if the frontend fails to launch.",
                "For a game-specific failure, verify the matching core and required firmware before changing the ROM destination.",
            )
        if status.marker:
            return ThreeDSAppHealth(
                "needs_attention",
                "Needs attention · Runtime assets only · Launchable core not verified",
                "RetroArch data/core files are visible, but a launchable frontend is not confirmed; the selected 3DS core may also be absent.",
                (
                    "Check the console for a RetroArch frontend/core entry and launch it directly.",
                    "Repair the frontend/core bundle through the maintained upstream or Universal-Updater path if the launchable core is absent or broken.",
                    "Then confirm the platform-specific core and firmware required by the selected game route.",
                ),
            )

    if key in {"luma", "homebrew-launcher", "godmode9"} and status.detected:
        return _detected_not_verified(
            status,
            f"{app.name} filesystem evidence is present, but RommHeld does not modify or operationally test this system-sensitive component.",
            "Use the maintained upstream/3DS Hacks Guide procedure for this component if it does not launch correctly.",
            "Avoid piecemeal replacement of boot-chain files from unrelated releases.",
            "Refresh readiness after completing the maintained recovery/update procedure.",
        )

    if key == "dsp-firmware" and status.detected:
        return _detected_not_verified(
            status,
            "A DSP firmware dump is present, but RommHeld cannot validate whether an application can consume it successfully.",
            "Regenerate the DSP firmware from this console using the maintained on-console procedure if applications still report DSP-related failures.",
            "Do not download another console's DSP dump.",
        )

    if status.detected:
        return _detected_not_verified(
            status,
            f"{app.name} is present, but RommHeld has not performed an on-console launch test.",
            "Launch the application directly on the console and confirm its normal startup path.",
            "If it fails, update or reinstall it using the maintained upstream installation method shown in readiness.",
            "Refresh RommHeld readiness after repair.",
        )

    if status.marker:
        return ThreeDSAppHealth(
            "needs_attention",
            "Needs attention · Partial evidence",
            f"RommHeld found files related to {app.name}, but they are not sufficient to prove a usable installation.",
            (
                "Use the application's maintained install/update path rather than assuming the existing files form a complete installation.",
                "After repair, launch it once on the console and refresh RommHeld readiness.",
            ),
        )

    return ThreeDSAppHealth(
        "missing",
        "Not verified",
        f"RommHeld has no reliable evidence that {app.name} is available from the checked sources.",
        (
            "Check the console directly if the application may be installed somewhere RommHeld cannot inspect.",
            "If it is absent or broken, use the preparation/updater/upstream action offered by readiness for this component.",
            "Refresh readiness after installation or repair.",
        ),
    )


__all__ = ["ThreeDSAppHealth", "assess_three_ds_app_health"]
