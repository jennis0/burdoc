
from logging import Logger
from typing import List, Dict, Any
from plotly.graph_objects import Figure


from .processor import Processor
from ..elements.layout_objects import LineElement
from ..elements.bbox import Bbox

class MarginProcessor(Processor):

    def __init__(self, logger: Logger):
        super().__init__("Margin", logger)

    
    def initialise(self):
        return super().initialise()

    def requirements(self) -> List[str]:
        return ["page_bounds", 'text']
    
    def generates(self) -> List[str]:
        return ['text', 'headers', 'footers', 'left_sidebar', 'right_sidebar', 'extracted_page_number']
    
    def _process_text(self, page_bound: Bbox, text: List[LineElement]) -> Dict[str, Any]:
        page_width = page_bound.width()
        page_height = page_bound.height()
        header_box = Bbox(0, 0, page_width, page_height*0.05, page_width, page_height)
        footer_box = Bbox(0, page_height*0.95, page_width, page_height, page_width, page_height)
        left_box = Bbox(0, 0, page_width*0.05, page_height, page_width, page_height)
        right_box = Bbox(page_width*0.95, 0, page_width, page_height, page_width, page_height)
        num_box = Bbox(0, page_height*0.92, page_width, page_height, page_width, page_height)
        res = {
            'headers':[],
            'footers':[],
            'left_sidebar':[],
            'right_sidebar':[],
            'extracted_page_number':None,
            'text':[]
        }
        for t in text:
            if t.bbox.overlap(header_box, 'first') > 0.95:
                res['headers'].append(t)
            elif t.bbox.overlap(num_box, 'first') > 0.95 and str.isnumeric(t.get_text()):
                res['extracted_page_number'] = int(t.get_text())
            elif t.bbox.overlap(footer_box, "first") > 0.95:
                res['footers'].append(t)
            elif t.bbox.overlap(left_box, 'first') > 0.95:
                res['left_sidebar'].append(t)
            elif t.bbox.overlap(right_box, 'first') > 0.95:
                res['right_sidebar'].append(t)
            else:
                res['text'].append(t)     

        return res       

    def process(self, data: Any) -> Any:
        data['headers'] = {}
        data['footers'] = {}
        data['left_sidebar'] = {}
        data['right_sidebar'] = {}
        data['extracted_page_number'] = {}

        for page_number, page_bound, text in self.get_page_data(data):
            res = self._process_text(page_bound, text)
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

