import abc
import logging
from typing import Dict, List, Tuple
from PIL import Image

from ...elements import Bbox, TableParts
from ...utils.logging import get_logger


class TableExtractorStrategy(abc.ABC):
    """Abstract base class defining the interface for table extraction methods. This is consistent between ML and rules based methods"""

    def __init__(self, name: str, log_level: int = logging.INFO):
        self.name = name
        self.log_level = log_level
        self.logger = get_logger(name, log_level=log_level)

    @staticmethod
    @abc.abstractmethod
    def requirements() -> List[str]:
        """Return list of data requirements for this strategy"""

    @abc.abstractmethod
    def extract_tables(self, page_numbers: List[int], page_images: Dict[int, Image.Image]) \
            -> Dict[int, List[List[Tuple[TableParts, Bbox]]]]:
        """Extracts tables and returns them in a complex JSON format
        """
