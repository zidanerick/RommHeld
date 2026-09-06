from __future__ import annotations

import inspect

from romm_vita_manager.three_ds_library import ThreeDSLibraryWidget


def test_three_ds_library_close_does_not_wait_on_network_threads():
    source = inspect.getsource(ThreeDSLibraryWidget.closeEvent)

    assert ".wait(" not in source
    assert "requestInterruption()" in source
    assert "_keep_worker_alive(worker)" in source
    assert "self.library_worker = None" in source
    assert "self.artwork_worker = None" in source
