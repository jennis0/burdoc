"""Composable processors used in the PDF processing chain."""

from .aggregator_processor import AggregatorProcessor
from .content_processor import ContentProcessor
from .json_out_processor import JSONOutProcessor
from .layout_processor import LayoutProcessor
from .margin_processor import MarginProcessor
from .pdf_load_processor.pdf_load_processor import PDFLoadProcessor
from .processor import Processor
from .reading_order_processor import ReadingOrderProcessor

try:
    from .table_processors.ml_table_processor import MLTableProcessor
    ML_PROCESSORS_LOADED=True
except Exception as e: #pylint: disable=W0718
    ML_PROCESSORS_LOADED=False
    
from .table_processors.rules_table_processor import RulesTableProcessor