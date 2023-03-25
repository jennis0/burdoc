import abc
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from ..utils.logging import get_logger


class TableExtractorStrategy(abc.ABC):

    class TableParts(Enum):
        Table = 0
        Column = 1
        Row = 2
        ColumnHeader = 3
        RowHeader = 4
        SpanningCell = 5

    def __init__(self, name: str, log_level: Optional[int]=logging.INFO):
        self.name = name
        self.log_level = log_level
        self.logger = get_logger(name, log_level=log_level)


    @abc.abstractmethod
    def requirements(self) -> List[str]:
        '''Return list of data requirements for this strategy'''
        pass

    @abc.abstractmethod
    def extract_tables(self, **kwargs) -> List[Dict[int, Any]]:
        '''Extracts tables and returns them in a complex JSON format'''
        pass