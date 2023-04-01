"""Utility functions for drawing a rendered page image and overlaying extracted elements"""
from typing import Any, Dict, List, Optional

from plotly.graph_objs import Figure
import plotly.express as plt

from ..elements import Bbox, Point
from ..processors.processor import Processor


def render_pages(data: Dict[str, Any], processors: List[Processor], pages: Optional[List[int]] = None):
    """Render an image of the page to the screen and apply the draw functions of all pass processors

    Args:
        data (Dict[str, Any]): Extracted content
        processors (List[Processor]): Processors used to overlay extraction elements
        pages (Optional[List[int]], optional): Pages to draw. Will draw all if None. Defaults to None.
    """
    if pages is None:
        pages = list(data['page_images'].keys())

    for page_number in pages:
        page_image = data['page_images'][page_number]
        fig = plt.imshow(page_image)
        for processor in processors:
            processor.add_generated_items_to_fig(page_number, fig, data)

        fig.update_layout({'showlegend': True, 'height': 1000, 'xaxis': {
                          'showticklabels': False}, 'yaxis': {'showticklabels': False}})
        fig.show()


def add_rect_to_figure(
    fig: Figure,
    bbox: Bbox,
    colour: str,
):
    """Add a rectangle to the passed figure

    Args:
        fig (Figure): A plotly figure
        bbox (Bbox): Bbox of rectangle to draw
        colour (str): Line colour
    """
    fig.add_shape(
        type='rect', xref='x', yref='y', opacity=0.6,
        x0=bbox.x0, y0=bbox.y0, x1=bbox.x1, y1=bbox.y1,
        line={'color': colour, 'width': 3}
    )


def add_text_to_figure(
    fig: Figure,
    point: Point,
    colour: str,
    text: str,
    text_size: float=20
):
    """Add text to the passed figure

    Args:
        fig (Figure): A plotly figure
        point (Point): Top left coordinates of the text
        colour (str): Text colour
    """
    fig.add_annotation({
        'font': {'color': colour, 'size': text_size},
        'x': point.x,
        'y': point.y,
        'showarrow': False,
        'font_family': "Arial Black",
        'text': text
    }
    )
