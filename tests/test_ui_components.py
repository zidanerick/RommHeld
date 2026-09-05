from romm_vita_manager.ui_components import status_tone


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
