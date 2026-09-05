from pathlib import Path


SOURCE = Path("romm_vita_manager/local_library.py")


def test_usb_planner_does_not_requeue_already_complete_vita_destinations() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'if state in {"INSTALLED", "STAGED"}:' in source
