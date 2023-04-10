from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, Optional

import numpy as np

from .bbox import Bbox
from .element import LayoutElement


class DrawingType(Enum):
    """Enumeration of types of drawing Burdoc understands.

    - LINE: Anything long and thin used as a visual separator
    - RECT: Usually means a square or outer edge defining an aside or section
    - TABLE: A collection of rectangles in a common table pattern
    - BULLET: A small circle indicating a textual bullet point.
    - UNKNOWN: An unknown drawing type
    """
    LINE = auto()
    RECT = auto()
    BULLET = auto()
    TABLE = auto()
    UNKNOWN = auto()


class DrawingElement(LayoutElement):
    """Core element representing a drawing"""

    def __init__(self, bbox: Bbox,
                 drawing_type: DrawingType = DrawingType.UNKNOWN,
                 fill_opacity: float = 0.0,
                 fill_colour: Optional[np.ndarray] = None,
                 stroke_opacity: float = 0.0,
                 stroke_colour: Optional[np.ndarray] = None,
                 stroke_width: Optional[float] = None):
        """Creates a drawing element.

        Args:
            bbox (Bbox): Bbox of the extent of the drawing
            opacity (float): Opacity of the drawing
            drawing_type (DrawingType, optional): Semantic purpose of the drawing. Default is UNKNOWN

        """
        super().__init__(bbox, title="Drawing")
        self.drawing_type = drawing_type
        self.fill_opacity = fill_opacity
        self.fill_colour = fill_colour
        self.stroke_opacity = stroke_opacity
        self.stroke_colour = stroke_colour
        self.stroke_width = stroke_width

    @staticmethod
    def from_dict(json_dict: Dict[str, Any], page_width: float, page_height: float,
                  type: DrawingType = DrawingType.UNKNOWN) -> DrawingElement:
        bbox = Bbox(*json_dict['rect'], page_width, page_height)
        drawing = DrawingElement(bbox, type)

        if 'f' in json_dict['type']:
            drawing.fill_opacity = json_dict['fill_opacity']
            drawing.fill_colour = json_dict['fill']

        if 's' in json_dict['type']:
            drawing.stroke_opacity = json_dict['stroke_opacity']
            drawing.stroke_colour = json_dict['color']
            drawing.stroke_width = json_dict['width']

        return drawing

    def __str__(self):
        extras = {"Type": self.drawing_type.name}
        return self._str_rep(extras)

    def to_json(self, extras: Optional[Dict] = None, include_bbox: bool = False, **kwargs):
        if not extras:
            extras = {}
        extras['type'] = self.drawing_type.name.lower()
        extras['stroke_opacity'] = self.stroke_opacity
        extras['fill_opacity'] = self.fill_opacity
        extras['fill_colour'] = self.fill_colour
        extras['stroke_colour'] = self.stroke_colour
        extras['stroke_width'] = self.stroke_width
        return super().to_json(**kwargs, extras=extras, include_bbox=include_bbox)
