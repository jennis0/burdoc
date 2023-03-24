import plotly.express as plt
from typing import Optional, Dict, Any,List
from logging import Logger
from ..processors.processor import Processor

def render_pages(logger: Logger, data: Dict[str, Any], processors: Processor, pages: Optional[List[int]]=None):
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