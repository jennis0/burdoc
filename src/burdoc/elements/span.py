import unicodedata
from typing import Any, Dict, Optional, cast

from .bbox import Bbox
from .element import LayoutElement
from .font import Font


class Span(LayoutElement):
    """Representation of a continuous run of text with the same
    font information.
    """

    def __init__(self, bbox: Bbox, text: str, font: Font):
        super().__init__(bbox, "Span")
        self.text = text
        self.font = font

    @staticmethod
    def from_dict(span_dict: Dict[str, Any], page_width: float, page_height: float):
        """Creates a Span from a PyMuPDF spac dictionary

        Args:
            span_dict (Dict[str, Any]): The PyMuPDF span dictionary
            page_width (float): Used to normalise bbox
            page_height (float): Used to normalise bbox

        Returns:
            Span
        """

        return Span(
            font=Font.from_dict(span_dict),
            text=unicodedata.normalize('NFKC', span_dict['text']),
            bbox=Bbox(span_dict['bbox'][0], span_dict['bbox'][1], span_dict['bbox'][2],
                      span_dict['bbox'][3], page_width, page_height),
        )

    def _str_rep(self, extras=None) -> str:
        if extras is None:
            extras = {}
        extras['text'] = self.text
        extras['font'] = self.font
        return super()._str_rep(extras)

    def to_json(self, extras: Optional[Dict[str, Any]] = None, include_bbox: bool = False, **kwargs):
        if not extras:
            extras = {}

        extras['text'] = self.text
        extras['font'] = self.font.to_json()
        return super().to_json(extras=extras, include_bbox=include_bbox, **kwargs)
