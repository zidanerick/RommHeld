from PySide6.QtCore import QCoreApplication

from romm_vita_manager import platform_services


def test_app_scoped_path_lookup_reasserts_rommheld_identity():
    original = QCoreApplication.applicationName()
    try:
        QCoreApplication.setApplicationName("pytest-transient-name")
        platform_services.cache_dir()
        assert QCoreApplication.applicationName() == platform_services.APP_NAME

        QCoreApplication.setApplicationName("another-transient-name")
        platform_services.config_dir()
        assert QCoreApplication.applicationName() == platform_services.APP_NAME
    finally:
        QCoreApplication.setApplicationName(original or platform_services.APP_NAME)
