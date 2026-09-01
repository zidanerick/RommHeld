from romm_vita_manager.file_transfer import transfer_file


def test_module_imports():
    assert callable(transfer_file)
