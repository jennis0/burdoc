import logging
import os
from typing import Optional

import logger_tt

set_logging = False

def get_logger(name:str, log_path: os.PathLike=".burdoc.log", log_level: Optional[int]=logging.INFO):
    global set_logging
    if not set_logging:
        logger_tt.setup_logging(
            log_path=log_path, suppress_level_below=log_level,
            full_context=2, capture_print=False,
            use_multiprocessing=True, suppress=['logger_tt', 'pytorch', 'timm', 'PIL', 'timm.models.helpers']
        )
    set_logging = True
    logger = logger_tt.getLogger(name)
    logger.setLevel(log_level)
    return logger
