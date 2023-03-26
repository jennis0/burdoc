from enum import Enum, auto
from typing import Dict, Optional

from .bbox import Bbox
from .element import LayoutElement

class DrawingType(Enum):
    """Enumeration of types of drawing Burdoc understands.
    LINE: Anything long and thin used as a visual separator
    RECT: Usually means a square or outer edge defining an aside or section
    BULLET: A small circle indicating a textual bullet point.
    """
    LINE = auto()
    RECT = auto()
    BULLET = auto()
    UNKNOWN = auto()


class DrawingElement(LayoutElement):
    """Core element representing a drawing"""
    
    def __init__(self, bbox: Bbox, opacity: float, drawing_type: DrawingType=DrawingType.UNKNOWN):
        """Creates a drawing element.

        Args:
            bbox (Bbox): Bbox of the extent of the drawing
            opacity (float): Opacity of the drawing
            drawing_type (DrawingType, optional): Semantic purpose of the drawing. Default is UNKNOWN
        """
        super().__init__(bbox, title="Drawing")
        self.drawing_type = drawing_type
        self.opacity = opacity
    
    def __str__(self):
        extras={"Type":self.drawing_type.name}
        return self._str_rep(extras)
    
    def to_json(self, extras: Optional[Dict]=None, include_bbox: bool=False, **kwargs):
        if not extras:
            extras = {}
        extras['type'] = self.drawing_type.name.lower()
        extras['opacity'] = self.opacity
        return super().to_json(**kwargs, extras=extras, include_bbox=include_bbox)
    