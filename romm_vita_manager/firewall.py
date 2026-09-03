from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class FirewallRule:
    backend: str
    zone: str | None
    source_ip: str
    port: int


class FirewallError(RuntimeError):
    pass


def _run(command: list[str], *, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise FirewallError(f"Required command is not installed: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise FirewallError(f"Firewall command timed out: {' '.join(command)}") from exc


def _pkexec(command: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    if shutil.which("pkexec") is None:
        raise FirewallError("pkexec is not installed, so RommHeld cannot request firewall permission automatically.")
    return _run(["pkexec", *command], timeout=timeout)


def _require_success(result: subprocess.CompletedProcess[str], action: str) -> None:
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout).strip()
    if not detail:
        detail = f"exit status {result.returncode}"
    raise FirewallError(f"{action}: {detail}")


def detect_backend() -> str | None:
    """Return the active supported firewall backend, if any."""
    if shutil.which("firewall-cmd"):
        result = _run(["firewall-cmd", "--state"])
        if result.returncode == 0 and result.stdout.strip().lower() == "running":
            return "firewalld"
    if shutil.which("ufw"):
        result = _run(["ufw", "status"])
        output = (result.stdout + "\n" + result.stderr).lower()
        if "status: active" in output:
            return "ufw"
    return None


def _firewalld_zone() -> str:
    result = _run(["firewall-cmd", "--get-default-zone"])
    _require_success(result, "Unable to determine the firewalld default zone")
    zone = result.stdout.strip()
    if not zone:
        raise FirewallError("firewalld returned an empty default zone.")
    return zone


def _firewalld_rich_rule(source_ip: str, port: int) -> str:
    return (
        f'rule family="ipv4" source address="{source_ip}" '
        f'port port="{port}" protocol="tcp" accept'
    )


def allow_temporary(source_ip: str, port: int) -> FirewallRule | None:
    """Allow one 3DS address to reach one TCP port for the current firewall runtime.

    firewalld runtime rules are intentionally used instead of permanent rules so a
    RommHeld crash or reboot cannot create a lasting open port. UFW is detected but
    not modified automatically because its normal allow rules are persistent.
    """
    backend = detect_backend()
    if backend is None:
        return None

    source_ip = source_ip.strip()
    if not source_ip:
        raise FirewallError("A 3DS IPv4 address is required for the temporary firewall rule.")
    if not (1 <= int(port) <= 65535):
        raise FirewallError(f"Invalid firewall port: {port}")

    if backend == "ufw":
        raise FirewallError(
            "UFW is active, but RommHeld will not create a persistent UFW rule automatically. "
            "Allow the selected TCP port from the 3DS address manually, then retry."
        )

    zone = _firewalld_zone()
    rule = _firewalld_rich_rule(source_ip, int(port))
    result = _pkexec(["firewall-cmd", f"--zone={zone}", f"--add-rich-rule={rule}"])
    _require_success(result, "Unable to temporarily allow the 3DS through firewalld")
    return FirewallRule("firewalld", zone, source_ip, int(port))


def remove_temporary(rule: FirewallRule | None) -> None:
    if rule is None:
        return
    if rule.backend != "firewalld" or not rule.zone:
        return

    rich_rule = _firewalld_rich_rule(rule.source_ip, rule.port)
    result = _pkexec(["firewall-cmd", f"--zone={rule.zone}", f"--remove-rich-rule={rich_rule}"])
    _require_success(result, "Unable to remove the temporary firewalld rule")
