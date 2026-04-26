import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from settings import AppSettings

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE_NAME = "tiamat.log"
LOG_MAX_BYTES = 1024 * 1024
LOG_BACKUP_COUNT = 3


def log_directory():
    return AppSettings.settings_dir() / "logs"


def log_path():
    return log_directory() / LOG_FILE_NAME


def configure_logging():
    logger = logging.getLogger("tiamat")
    if logger.handlers:
        return logger

    log_directory().mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path(),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    return logger


def install_exception_hooks(logger=None):
    logger = logger or logging.getLogger("tiamat")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Unhandled exception in main thread.",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def handle_thread_exception(args):
        logger.critical(
            "Unhandled exception in background thread.",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
