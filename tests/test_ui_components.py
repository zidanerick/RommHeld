from romm_vita_manager.design_tokens import (
    health_state_label,
    health_state_tone,
    normalize_health_state,
    status_tone,
)


def test_status_tone_marks_successful_states() -> None:
    assert status_tone("Ready") == "success"
    assert status_tone("USB mounted") == "success"
    assert status_tone("FTP configured") == "success"
    assert status_tone("Transfer completed") == "success"


def test_status_tone_keeps_absence_states_muted() -> None:
    assert status_tone("Not mounted") == "muted"
    assert status_tone("Not configured") == "muted"
    assert status_tone("Not detected") == "muted"
    assert status_tone("Destination unavailable") == "muted"


def test_status_tone_distinguishes_busy_and_failure_states() -> None:
    assert status_tone("Checking…") == "warning"
    assert status_tone("Action required") == "warning"
    assert status_tone("Endpoint required") == "warning"
    assert status_tone("Validation failed") == "error"
    assert status_tone("Invalid endpoint") == "error"


def test_status_tone_is_neutral_for_unclassified_text() -> None:
    assert status_tone("") == "neutral"
    assert status_tone("Idle") == "neutral"


def test_explicit_health_vocab_covers_current_ds_and_vita_services() -> None:
    assert health_state_tone("verified") == "success"
    assert health_state_tone("not_verified") == "neutral"
    assert health_state_tone("present_unverified") == "neutral"
    assert health_state_tone("needs_attention") == "warning"
    assert health_state_tone("data_only") == "warning"
    assert health_state_tone("outdated") == "warning"
    assert health_state_tone("misconfigured") == "error"
    assert health_state_tone("missing") == "muted"
    assert health_state_tone("unknown") == "muted"
    assert health_state_tone("not_applicable") == "muted"


def test_explicit_health_vocab_uses_stable_readable_labels() -> None:
    assert normalize_health_state("present-unverified") == "present_unverified"
    assert health_state_label("present_unverified") == "Present · Launch not verified"
    assert health_state_label("data-only") == "Data/assets only"
    assert health_state_label("unknown") == "Not checked"
    assert health_state_label("not-applicable") == "Not applicable"
