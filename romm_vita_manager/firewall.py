from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class FirewallRule:
    backend: str
    zone: str | None
    source_ip: str
    port: int
    destination_ip: str | None = None


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


def _command_path(name: str, fallbacks: tuple[str, ...] = ()) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    for candidate in fallbacks:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _pkexec(command: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    pkexec = _command_path("pkexec", ("/usr/bin/pkexec", "/usr/bin/pkexec"))
    if pkexec is None:
        raise FirewallError("pkexec is not installed, so RommHeld cannot request firewall permission automatically.")
    return _run([pkexec, *command], timeout=timeout)


def _require_success(result: subprocess.CompletedProcess[str], action: str) -> None:
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout).strip()
    if not detail:
        detail = f"exit status {result.returncode}"
    raise FirewallError(f"{action}: {detail}")


def detect_backend() -> str | None:
    """Return the active supported firewall backend, if any."""
    firewalld = _command_path("firewall-cmd", ("/usr/bin/firewall-cmd", "/usr/sbin/firewall-cmd"))
    if firewalld:
        result = _run([firewalld, "--state"])
        if result.returncode == 0 and result.stdout.strip().lower() == "running":
            return "firewalld"

    ufw = _command_path("ufw", ("/usr/sbin/ufw", "/usr/bin/ufw"))
    if ufw:
        result = _run([ufw, "status"])
        output = (result.stdout + "\n" + result.stderr).lower()
        if "status: active" in output:
            return "ufw"
    return None


def _firewalld_command() -> str:
    command = _command_path("firewall-cmd", ("/usr/bin/firewall-cmd", "/usr/sbin/firewall-cmd"))
    if command is None:
        raise FirewallError("firewall-cmd is not installed.")
    return command


def _ufw_command() -> str:
    command = _command_path("ufw", ("/usr/sbin/ufw", "/usr/bin/ufw"))
    if command is None:
        raise FirewallError("ufw is not installed.")
    return command


def _firewalld_zone() -> str:
    result = _run([_firewalld_command(), "--get-default-zone"])
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


def _ufw_rule_args(source_ip: str, port: int, destination_ip: str | None) -> list[str]:
    return [
        _ufw_command(),
        "allow",
        "from",
        source_ip,
        "to",
        destination_ip or "any",
        "port",
        str(port),
        "proto",
        "tcp",
    ]


def _ufw_delete_args(source_ip: str, port: int, destination_ip: str | None) -> list[str]:
    return [
        _ufw_command(),
        "delete",
        "allow",
        "from",
        source_ip,
        "to",
        destination_ip or "any",
        "port",
        str(port),
        "proto",
        "tcp",
    ]


def allow_temporary(source_ip: str, port: int, *, destination_ip: str | None = None) -> FirewallRule | None:
    """Allow one 3DS address to reach one TCP port for the current transfer."""
    backend = detect_backend()
    if backend is None:
        return None

    source_ip = source_ip.strip()
    destination_ip = destination_ip.strip() if destination_ip else None
    if not source_ip:
        raise FirewallError("A 3DS IPv4 address is required for the temporary firewall rule.")
    if not (1 <= int(port) <= 65535):
        raise FirewallError(f"Invalid firewall port: {port}")

    if backend == "firewalld":
        zone = _firewalld_zone()
        rule = _firewalld_rich_rule(source_ip, int(port))
        result = _pkexec([_firewalld_command(), f"--zone={zone}", f"--add-rich-rule={rule}"])
        _require_success(result, "Unable to temporarily allow the 3DS through firewalld")
        return FirewallRule("firewalld", zone, source_ip, int(port), destination_ip)

    result = _pkexec(_ufw_rule_args(source_ip, int(port), destination_ip))
    _require_success(result, "Unable to temporarily allow the 3DS through UFW")
    return FirewallRule("ufw", None, source_ip, int(port), destination_ip)


def remove_temporary(rule: FirewallRule | None) -> None:
    if rule is None:
        return
    if rule.backend == "firewalld":
        if not rule.zone:
            return
        rich_rule = _firewalld_rich_rule(rule.source_ip, rule.port)
        result = _pkexec([_firewalld_command(), f"--zone={rule.zone}", f"--remove-rich-rule={rich_rule}"])
        _require_success(result, "Unable to remove the temporary firewalld rule")
        return
    if rule.backend == "ufw":
        result = _pkexec(_ufw_delete_args(rule.source_ip, rule.port, rule.destination_ip))
        _require_success(result, "Unable to remove the temporary UFW rule")
