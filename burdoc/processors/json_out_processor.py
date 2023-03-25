import logging
from typing import List, Dict, Any, Optional
from plotly.graph_objects import Figure
import os
from ..elements.element import LayoutElement
from .processor import Processor

class JSONOutProcessor(Processor):

    def __init__(self, log_level: Optional[int]=logging.INFO):
        super().__init__("json-out", log_level=log_level)

    def initialise(self):
        return super().initialise()
    
    def requirements(self) -> List[str]:
        return ['elements', 'image_store']
    
    def generates(self) -> List[str]:
        return ['content', 'image_store']
    
    def _to_json(self, elements: List[LayoutElement]):
        return [e.to_json() for e in elements]

    def process(self, data: Any) -> Any:
        data['content'] = {}
        for page_number, elements, image_store in self.get_page_data(data):
            data['content'][page_number] = self._to_json(elements)


            if len(image_store) == 0:
                continue

            image_root = "image_out"
            if not os.path.exists(image_root):
                os.makedirs(image_root)
            image_paths = []
            for i,im in enumerate(image_store):
                path = f"image_{page_number}_{i}.webp"
                im.save(os.path.join(image_root, path))
                image_paths.append(path)
            data['image_store'][page_number] = image_paths
        return data
    
    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        return
