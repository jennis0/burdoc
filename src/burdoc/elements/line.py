from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .bbox import Bbox
from .element import LayoutElement
from .span import Span


class LineElement(LayoutElement):
    """Core element representing a line of text"""

    bbox: Bbox
    spans: List[Span]
    rotation: Tuple[float, float]

    def __init__(self, bbox: Bbox, spans: List[Span], rotation: Tuple[float, float]):
        """Creates a line element

        Args:
            bbox (Bbox): Bbox of the extent of the line
            spans (List[Span]): List of text spans within the line, separation into
                spans implies a change in font.
            rotation (List[float]): Degree of rotation from the x-axis
        """
        super().__init__(bbox, title="Line")
        self.spans = spans
        self.rotation = rotation

    @staticmethod
    def from_dict(line_dict: Dict[str, Any], page_width: float, page_height: float) -> LineElement:
        """Create a LineElement from a PyMuPDF line dictionary

        Args:
            line_dict (Dict[str, Any]): The PyMuPDF dictionary
            page_width (float): Used to normalise bbox
            page_height (float): Used to normalise bbox

        Returns:
            LineElement
        """
        return LineElement(
            spans=[Span.from_dict(s, page_width, page_height) for s in line_dict['spans']],
            bbox=Bbox(line_dict['bbox'][0], line_dict['bbox'][1], line_dict['bbox'][2],
                      line_dict['bbox'][3], page_width, page_height),
            rotation=line_dict['dir']
        )

    def get_text(self) -> str:
        """Returns all text contained within the line as a string.
        This strips out any format or font information.

        Returns:
            str
        """
        if len(self.spans) > 0:
            return "".join([s.text for s in self.spans])
        return ""

    def __str__(self):
        extras = {"Text": self.spans[0].text if len(self.spans) > 0 else ''}
        return self._str_rep(extras)

    def to_json(self, extras: Optional[Dict] = None, include_bbox: bool = False, **kwargs):
        if not extras:
            extras = {}
        extras['spans'] = [s.to_json() for s in self.spans]
        return super().to_json(**kwargs, extras=extras, include_bbox=include_bbox)
