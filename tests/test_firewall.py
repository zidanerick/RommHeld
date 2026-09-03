from __future__ import annotations

from unittest.mock import patch

from romm_vita_manager.firewall import (
    FirewallRule,
    _firewalld_rich_rule,
    _ufw_delete_args,
    _ufw_rule_args,
    allow_temporary,
    remove_temporary,
)


def test_firewalld_rich_rule_is_source_and_port_specific() -> None:
    rule = _firewalld_rich_rule("10.0.0.141", 8080)
    assert rule == 'rule family="ipv4" source address="10.0.0.141" port port="8080" protocol="tcp" accept'


def test_allow_temporary_uses_runtime_firewalld_rule() -> None:
    with patch("romm_vita_manager.firewall.detect_backend", return_value="firewalld"), patch(
        "romm_vita_manager.firewall._firewalld_zone", return_value="public"
    ), patch("romm_vita_manager.firewall._pkexec") as pkexec, patch(
        "romm_vita_manager.firewall._command_path", return_value="/usr/bin/firewall-cmd"
    ):
        pkexec.return_value.returncode = 0
        result = allow_temporary("10.0.0.141", 8080)

    assert result == FirewallRule("firewalld", "public", "10.0.0.141", 8080, None)
    pkexec.assert_called_once_with(
        [
            "/usr/bin/firewall-cmd",
            "--zone=public",
            '--add-rich-rule=rule family="ipv4" source address="10.0.0.141" port port="8080" protocol="tcp" accept',
        ]
    )


def test_allow_temporary_uses_source_and_destination_specific_ufw_rule() -> None:
    with patch("romm_vita_manager.firewall._command_path", return_value="/usr/sbin/ufw"):
        args = _ufw_rule_args("10.0.0.141", 8000, "10.0.0.21")
    assert args == [
        "/usr/sbin/ufw",
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

    with patch("romm_vita_manager.firewall.detect_backend", return_value="ufw"), patch(
        "romm_vita_manager.firewall._pkexec"
    ) as pkexec, patch("romm_vita_manager.firewall._command_path", return_value="/usr/sbin/ufw"):
        pkexec.return_value.returncode = 0
        result = allow_temporary("10.0.0.141", 8000, destination_ip="10.0.0.21")

    assert result == FirewallRule("ufw", None, "10.0.0.141", 8000, "10.0.0.21")
    pkexec.assert_called_once_with(
        [
            "/usr/sbin/ufw",
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


def test_remove_temporary_removes_same_ufw_rule() -> None:
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


def test_remove_temporary_removes_the_same_runtime_firewalld_rule() -> None:
    rule = FirewallRule("firewalld", "public", "10.0.0.141", 8080)
    with patch("romm_vita_manager.firewall._pkexec") as pkexec, patch(
        "romm_vita_manager.firewall._command_path", return_value="/usr/bin/firewall-cmd"
    ):
        pkexec.return_value.returncode = 0
        remove_temporary(rule)

    pkexec.assert_called_once_with(
        [
            "/usr/bin/firewall-cmd",
            "--zone=public",
            '--remove-rich-rule=rule family="ipv4" source address="10.0.0.141" port port="8080" protocol="tcp" accept',
        ]
    )
