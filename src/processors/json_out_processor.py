from logging import Logger
from typing import List, Dict, Any
from plotly.graph_objects import Figure

from ..elements.element import LayoutElement
from .processor import Processor

class JSONOutProcessor(Processor):

    def __init__(self, logger: Logger):
        super().__init__("json-out", logger)

    def initialise(self):
        return super().initialise()
    
    def requirements(self) -> List[str]:
        return ['elements']
    
    def generates(self) -> List[str]:
        return ['json']
    
    def _to_json(self, elements: List[LayoutElement]):
        return [e.to_json() for e in elements]

    def process(self, data: Any) -> Any:
        data['json'] = {}
        for page_number, elements in self.get_page_data(data):
            data['json'][page_number] = self._to_json(elements)
        return data
    
    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        return
