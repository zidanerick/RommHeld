from __future__ import annotations

from unittest.mock import patch

from romm_vita_manager.firewall import (
    FirewallRule,
    _firewalld_rich_rule,
    _ufw_delete_args,
    _ufw_rule_args,
    allow_persistent,
    allow_temporary,
    remove_temporary,
)


def test_firewalld_rich_rule_is_source_and_port_specific() -> None:
    rule = _firewalld_rich_rule("10.0.0.141", 8080)
    assert rule == 'rule family="ipv4" source address="10.0.0.141" port port="8080" protocol="tcp" accept'


def test_allow_persistent_creates_permanent_and_runtime_firewalld_rule_once() -> None:
    with patch("romm_vita_manager.firewall.detect_backend", return_value="firewalld"), patch(
        "romm_vita_manager.firewall._firewalld_zone", return_value="public"
    ), patch("romm_vita_manager.firewall._pkexec") as pkexec, patch(
        "romm_vita_manager.firewall._command_path", return_value="/usr/bin/firewall-cmd"
    ), patch(
        "romm_vita_manager.firewall._persistent_rule_was_installed", return_value=False
    ), patch("romm_vita_manager.firewall._remember_persistent_rule") as remember:
        pkexec.return_value.returncode = 0
        result = allow_persistent("10.0.0.141", 8080)

    assert result == FirewallRule("firewalld", "public", "10.0.0.141", 8080, None, True)
    assert pkexec.call_count == 2
    pkexec.assert_any_call(
        [
            "/usr/bin/firewall-cmd",
            "--zone=public",
            "--permanent",
            '--add-rich-rule=rule family="ipv4" source address="10.0.0.141" port port="8080" protocol="tcp" accept',
        ]
    )
    pkexec.assert_any_call(
        [
            "/usr/bin/firewall-cmd",
            "--zone=public",
            '--add-rich-rule=rule family="ipv4" source address="10.0.0.141" port port="8080" protocol="tcp" accept',
        ]
    )
    remember.assert_called_once_with(result)


def test_existing_persistent_rule_skips_elevation() -> None:
    with patch("romm_vita_manager.firewall.detect_backend", return_value="firewalld"), patch(
        "romm_vita_manager.firewall._firewalld_zone", return_value="public"
    ), patch(
        "romm_vita_manager.firewall._persistent_rule_was_installed", return_value=True
    ), patch("romm_vita_manager.firewall._pkexec") as pkexec:
        result = allow_persistent("10.0.0.141", 8080)

    assert result is not None and result.persistent
    pkexec.assert_not_called()


def test_allow_persistent_uses_source_and_destination_specific_ufw_rule() -> None:
    with patch("romm_vita_manager.firewall._command_path", return_value="/usr/sbin/ufw"):
        args = _ufw_rule_args("10.0.0.141", 8080, "10.0.0.21")
    assert args == [
        "/usr/sbin/ufw",
        "allow",
        "from",
        "10.0.0.141",
        "to",
        "10.0.0.21",
        "port",
        "8080",
        "proto",
        "tcp",
    ]

    with patch("romm_vita_manager.firewall.detect_backend", return_value="ufw"), patch(
        "romm_vita_manager.firewall._pkexec"
    ) as pkexec, patch("romm_vita_manager.firewall._command_path", return_value="/usr/sbin/ufw"), patch(
        "romm_vita_manager.firewall._persistent_rule_was_installed", return_value=False
    ), patch("romm_vita_manager.firewall._remember_persistent_rule"):
        pkexec.return_value.returncode = 0
        result = allow_persistent("10.0.0.141", 8080, destination_ip="10.0.0.21")

    assert result == FirewallRule("ufw", None, "10.0.0.141", 8080, "10.0.0.21", True)
    pkexec.assert_called_once_with(
        [
            "/usr/sbin/ufw",
            "allow",
            "from",
            "10.0.0.141",
            "to",
            "10.0.0.21",
            "port",
            "8080",
            "proto",
            "tcp",
        ]
    )


def test_legacy_allow_temporary_now_returns_persistent_rule() -> None:
    expected = FirewallRule("ufw", None, "10.0.0.141", 8080, None, True)
    with patch("romm_vita_manager.firewall.allow_persistent", return_value=expected) as persistent:
        assert allow_temporary("10.0.0.141", 8080) == expected
    persistent.assert_called_once_with("10.0.0.141", 8080, destination_ip=None)


def test_remove_temporary_keeps_persistent_rule() -> None:
    rule = FirewallRule("ufw", None, "10.0.0.141", 8080, "10.0.0.21", True)
    with patch("romm_vita_manager.firewall._pkexec") as pkexec:
        remove_temporary(rule)
    pkexec.assert_not_called()


def test_remove_temporary_still_removes_legacy_ufw_rule() -> None:
    rule = FirewallRule("ufw", None, "10.0.0.141", 8000, "10.0.0.21")
    with patch("romm_vita_manager.firewall._pkexec") as pkexec, patch(
        "romm_vita_manager.firewall._command_path", return_value="/usr/sbin/ufw"
    ):
        pkexec.return_value.returncode = 0
        remove_temporary(rule)

    pkexec.assert_called_once_with(
        [
            "/usr/sbin/ufw",
            "delete",
            "allow",
            "from",
            "10.0.0.141",
            "to",
            "10.0.0.21",
            "port",
            "8000",
            "proto",
            "tcp",
        ]
    )
