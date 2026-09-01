from romm_vita_manager.file_transfer import transfer_file


def test_transfer_helper_is_callable():
    assert callable(transfer_file)
