import importlib.util

from .rules_table_processor import RulesTableProcessor
from .table_extractor_strategy import TableExtractorStrategy

if importlib.util.find_spec('torch') is not None:
    from .detr_table_strategy import DetrTableStrategy
    from .ml_table_processor import MLTableProcessor
    LOADED_ML_PROCESSORS=True
else:
    MLTableProcessor=None #type:ignore #pylint: disable=C0103 
    DetrTableStrategy=None  #type:ignore #pylint: disable=C0103
    LOADED_ML_PROCESSORS=False