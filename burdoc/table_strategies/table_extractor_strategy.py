import abc
import logging
from enum import Enum
from typing import Any, List, Dict

class TableExtractorStrategy(abc.ABC):

    class TableParts(Enum):
        Table = 0
        Column = 1
        Row = 2
        ColumnHeader = 3
        RowHeader = 4
        SpanningCell = 5

    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self.logger = logger


    @abc.abstractmethod
    def requirements(self) -> List[str]:
        '''Return list of data requirements for this strategy'''
        pass

    @abc.abstractmethod
    def extract_tables(self, **kwargs) -> List[Dict[int, Any]]:
        '''Extracts tables and returns them in a complex JSON format'''
        pass