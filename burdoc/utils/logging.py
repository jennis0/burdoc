import logging
import logger_tt

SET_LOGGING = False

def get_logger(name:str, log_path: str=".burdoc.log", log_level: int=logging.DEBUG):
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
