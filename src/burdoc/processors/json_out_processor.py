import logging
from typing import Any, Dict, List, Tuple

from plotly.graph_objects import Figure

from ..elements.element import LayoutElement
from .processor import Processor


class JSONOutProcessor(Processor):
    """Converts generated elements and images into a JSON-compatible structure

    Requires: ["elements", "images"]
    Optional: []
    Generators: ["content"]
    """

    name: str = "json-out"

    def __init__(self, log_level: int = logging.INFO):
        super().__init__(JSONOutProcessor.name, log_level=log_level)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (['elements'], [])

    def generates(self) -> List[str]:
        return ['content']

    def _to_json(self, elements: List[LayoutElement]) -> List[Dict[str, Any]]:
        return [e.to_json() for e in elements]

    def _process(self, data: Any) -> Any:
        data['content'] = {}
        for page_number, elements in self.get_page_data(data):
            data['content'][page_number] = self._to_json(elements)
        return data

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        return
