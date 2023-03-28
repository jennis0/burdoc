import logging
import base64
from typing import Any, Dict, List, Tuple
from PIL.Image import Image

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

    def __init__(self, extract_images: bool, log_level: int=logging.INFO):
        super().__init__(JSONOutProcessor.name, log_level=log_level)
        self.extract_images = extract_images
    
    def requirements(self) -> Tuple[List[str], List[str]]:
        return (['elements', 'images'], [])
    
    def generates(self) -> List[str]:
        return ['content', 'images']
    
    def _to_json(self, elements: List[LayoutElement]) -> List[Dict[str, Any]]:
        return [e.to_json() for e in elements]

    def _process(self, data: Any) -> Any:
        data['content'] = {}
        for page_number, elements, image_store in self.get_page_data(data):
            data['content'][page_number] = self._to_json(elements)


            if len(image_store) == 0 or not self.extract_images:
                continue

            image: Image
            for i,image in enumerate(image_store):
                image_store[i] = base64.encodebytes(image.tobytes()).decode("utf-8")
        return data
    
    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        return
