"""Utility function for retrieving a tt_logger that can manage across threads"""

import logging

import logger_tt

SET_LOGGING = False


def get_logger(name: str, log_path: str = ".burdoc.log", log_level: int = logging.INFO):
    """Retrieve a threadsafe logger.

    Args:
        name (str): Name of the logger
        log_path (str, optional): Write path for the log file. Defaults to ".burdoc.log".
        log_level (int, optional): Log level. Defaults to logging.INFO.

    Returns:
        _type_: _description_
    """
    global SET_LOGGING
    if not SET_LOGGING:
        logger_tt.setup_logging(
            log_path=log_path, suppress_level_below=log_level,
            full_context=2, capture_print=False,
            use_multiprocessing=True, suppress=['logger_tt', 'pytorch', 'timm', 'PIL', 'timm.models.helpers']
        )
    SET_LOGGING = True
    logger = logger_tt.getLogger(name)
    logger.setLevel(log_level)
    return logger
