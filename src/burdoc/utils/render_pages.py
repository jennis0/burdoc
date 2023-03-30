from typing import Any, Dict, List, Optional

from plotly.graph_objs import Figure
import plotly.express as plt

from ..elements import Bbox, Point
from ..processors.processor import Processor


def render_pages(data: Dict[str, Any], processors: List[Processor], pages: Optional[List[int]]=None):
        '''Render an image of the page to the screen, highlighting elements'''

        if pages is None:
               pages = list(data['page_images'].keys())

        for page_number in pages:
            pi = data['page_images'][page_number]
            fig = plt.imshow(pi)
            for p in processors:
                p.add_generated_items_to_fig(page_number, fig, data)
        
            fig.update_layout({'showlegend': True, 'height':1000, 'xaxis':{'showticklabels':False}, 'yaxis':{'showticklabels':False}})
            fig.show()
            
def add_rect_to_figure(
        fig: Figure, 
        bbox: Bbox, 
        colour: str, 
    ):
    fig.add_shape(
        type='rect', xref='x', yref='y', opacity=0.6,
        x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
        line=dict(color=colour, width=3)
    )
    
def add_text_to_figure(
        fig: Figure, 
        point: Point, 
        colour: str, 
        text: str
    ):
    fig.add_annotation(dict(font=dict(color=colour,size=20),
                            x=point.x,
                            y=point.y,
                            showarrow=False,
                            font_family="Arial Black",
                            text=text))