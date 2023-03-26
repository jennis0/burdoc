
import logging
from typing import Any, Dict, List, Optional, Tuple

from plotly.graph_objects import Figure

from ..elements.bbox import Bbox
from ..elements.element import LayoutElement
from ..elements.line import LineElement
from ..utils.layout_graph import LayoutGraph
from .processor import Processor


class MarginProcessor(Processor):
    """Identifies headers, footers, and marginalia

    Requires: ['page_bounds', 'text_elements']
    Optional: ['tables']
    Generates: ['text_elements', 'headers', 'footers', 'left_sidebar', 'right_sidebar', 'extracted_page_number']
    """
    
    name: str = "margin"

    def __init__(self, log_level: int=logging.INFO):
        super().__init__(MarginProcessor.name, log_level=log_level)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (["page_bounds", 'text_elements'], ['tables'])
    
    def generates(self) -> List[str]:
        return ['text_elements', 'headers', 'footers', 'left_sidebar', 'right_sidebar', 'extracted_page_number']
    
    def _process_text(self, page_bound: Bbox, text: List[LineElement], other_elements: Optional[List[LayoutElement]]) -> Dict[str, Any]:
        page_width = page_bound.width()
        page_height = page_bound.height()
        res = {
            'headers':[],
            'footers':[],
            'left_sidebar':[],
            'right_sidebar':[],
            'extracted_page_number':None,
            'text_elements':[]
        }

        if other_elements:
            layout_graph = LayoutGraph(self.logger, page_bound, text + other_elements)
        else:
            layout_graph = LayoutGraph(self.logger, page_bound, text)
            
        for node in layout_graph.nodes[1:]:
            t = node.element
            if not isinstance(t, LineElement):
                continue

            if len(node.up) > 0:
                nearest_up = node.up[0][1]
            else:
                nearest_up = 10000
            
            if len(node.down) > 0:
                nearest_down = node.down[0][1]
            else:
                nearest_down = 10000

            nearest = min(nearest_down, nearest_up)

            top = t.bbox.y1 / page_height
            bottom = t.bbox.y0 / page_height
            left = t.bbox.x1 / page_width
            right = t.bbox.x0 / page_width
            
            if top < 0.05 and nearest > 5:
                res['headers'].append(t)

            elif top < 0.1 and nearest > 10 and t.spans[0].font.size < 10:
                res['headers'].append(t)

            elif bottom > 0.9 and nearest > 5:
                if str.isnumeric(t.get_text()):
                    res['extracted_page_number'] = int(t.get_text())
                else:
                    res['footers'].append(t)

            elif right > 0.95 or t.rotation[0] < 0.7 and right > 0.9:
                res['right_sidebar'].append(t)

            elif left < 0.05 or t.rotation[0] < 0.7 and left < 0.1:
                res['left_sidebar'].append(t)

            else:
                res['text_elements'].append(t)     

        return res       

    def _process(self, data: Any) -> Any:
        data['headers'] = {}
        data['footers'] = {}
        data['left_sidebar'] = {}
        data['right_sidebar'] = {}
        data['extracted_page_number'] = {}

        for page_number, page_bound, text, tables in self.get_page_data(data):
            res = self._process_text(page_bound, text, tables)
            for t in res:
                data[t][page_number] = res[t]

        return data


    def add_generated_items_to_fig(self, page_number:int, fig: Figure, data: Dict[str, Any]):

        colours = {
            'headers':'violet',
            'footers':'violet',
            'left_sidebar':'pink',
            'right_sidebar':'pink',
        }

        def add_rect(fig, bbox, colour):
            fig.add_shape(
                type='rect', xref='x', yref='y', opacity=0.6,
                x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
                line=dict(color=colour, width=3)
            )

        for field in ['headers', 'footers', 'left_sidebar', 'right_sidebar']:
            for e in data[field][page_number]:
                add_rect(fig, e.bbox, colours[field])

        fig.add_scatter(x=[None], y=[None], name="Footers", line=dict(width=3, color=colours['headers']))
        fig.add_scatter(x=[None], y=[None], name="Headers", line=dict(width=3, color=colours['footers']))
        fig.add_scatter(x=[None], y=[None], name="Sidebars", line=dict(width=3, color=colours['left_sidebar']))

