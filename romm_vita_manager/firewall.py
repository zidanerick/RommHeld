from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import APP_DIR


_STATE_PATH = APP_DIR / "fbi_firewall_rules.json"


@dataclass(frozen=True)
class FirewallRule:
    backend: str
    zone: str | None
    source_ip: str
    port: int
    destination_ip: str | None = None
    persistent: bool = False


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
    pkexec = _command_path("pkexec", ("/usr/bin/pkexec",))
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


def _ufw_enabled_from_config() -> bool:
    """Detect UFW's enabled state without invoking a root-only UFW command."""
    config_path = Path("/etc/ufw/ufw.conf")
    try:
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip().upper() == "ENABLED":
                return value.strip().lower() == "yes"
    except OSError:
        return False
    return False


def detect_backend() -> str | None:
    """Return the active supported firewall backend without requiring root."""
    firewalld = _command_path("firewall-cmd", ("/usr/bin/firewall-cmd", "/usr/sbin/firewall-cmd"))
    if firewalld:
        result = _run([firewalld, "--state"])
        if result.returncode == 0 and result.stdout.strip().lower() == "running":
            return "firewalld"

    ufw = _command_path("ufw", ("/usr/sbin/ufw", "/usr/bin/ufw"))
    if ufw and _ufw_enabled_from_config():
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


def _rule_key(rule: FirewallRule) -> str:
    return "|".join(
        (
            rule.backend,
            rule.zone or "",
            rule.source_ip,
            rule.destination_ip or "",
            str(rule.port),
        )
    )


def _load_persistent_rules() -> dict[str, dict]:
    try:
        value = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _remember_persistent_rule(rule: FirewallRule) -> None:
    state = _load_persistent_rules()
    state[_rule_key(rule)] = asdict(rule)
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = _STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(_STATE_PATH)


def _persistent_rule_was_installed(rule: FirewallRule) -> bool:
    return _rule_key(rule) in _load_persistent_rules()


def allow_persistent(source_ip: str, port: int, *, destination_ip: str | None = None) -> FirewallRule | None:
    """Create a persistent FBI HTTP rule once and reuse it on later transfers.

    The rule remains narrowly scoped to the configured 3DS IPv4 address and
    serving TCP port. RommHeld records successful creation in its local config
    directory so routine FBI sends do not repeatedly trigger an elevation
    prompt. If the 3DS address changes, a new scoped rule is created.
    """
    backend = detect_backend()
    if backend is None:
        return None

    source_ip = source_ip.strip()
    destination_ip = destination_ip.strip() if destination_ip else None
    if not source_ip:
        raise FirewallError("A 3DS IPv4 address is required for the FBI firewall rule.")
    if not (1 <= int(port) <= 65535):
        raise FirewallError(f"Invalid firewall port: {port}")

    zone = _firewalld_zone() if backend == "firewalld" else None
    rule = FirewallRule(backend, zone, source_ip, int(port), destination_ip, True)
    if _persistent_rule_was_installed(rule):
        return rule

    if backend == "firewalld":
        rich_rule = _firewalld_rich_rule(source_ip, int(port))
        permanent = _pkexec(
            [
                _firewalld_command(),
                f"--zone={zone}",
                "--permanent",
                f"--add-rich-rule={rich_rule}",
            ]
        )
        _require_success(permanent, "Unable to permanently allow FBI Remote Install through firewalld")
        runtime = _pkexec(
            [_firewalld_command(), f"--zone={zone}", f"--add-rich-rule={rich_rule}"]
        )
        _require_success(runtime, "Unable to activate the FBI Remote Install firewalld rule")
    else:
        result = _pkexec(_ufw_rule_args(source_ip, int(port), destination_ip))
        _require_success(result, "Unable to permanently allow FBI Remote Install through UFW")

    _remember_persistent_rule(rule)
    return rule


def allow_temporary(source_ip: str, port: int, *, destination_ip: str | None = None) -> FirewallRule | None:
    """Compatibility wrapper for older callers; FBI rules are now persistent."""
    return allow_persistent(source_ip, port, destination_ip=destination_ip)


def remove_temporary(rule: FirewallRule | None) -> None:
    """Remove legacy temporary rules; persistent FBI rules intentionally remain."""
    if rule is None or rule.persistent:
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
