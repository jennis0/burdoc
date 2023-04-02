from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .bbox import Bbox
from .element import LayoutElementGroup
from .line import LineElement


class TextBlockType(Enum):
    """Possible types of text supported by the semantic classifier.
    """
    SMALL = auto()
    PARAGRAPH = auto()
    H1 = auto()
    H2 = auto()
    H3 = auto()
    H4 = auto()
    H5 = auto()
    H6 = auto()
    EMPHASIS = auto()


class TextBlock(LayoutElementGroup):
    """Represents a standard grouping of lines into a paragraph. All text
    within a textblock can be considered to be of semantically equivalent
    fonts. This may include variations in bold or italics."""

    items: List[LineElement]  # type:ignore

    def __init__(self,
                 bbox: Optional[Bbox] = None,
                 items: Optional[List[LineElement]] = None,
                 text_type: TextBlockType = TextBlockType.PARAGRAPH
                 ):
        super().__init__(bbox, items, title="TextBlock")  # type:ignore
        self.type = text_type

    def get_text(self) -> str:
        """Returns all text contained within the block as a string
        This strips out any format or font information.

        Returns:
            str
        """
        return " ".join(i.get_text() for i in self.items)

    def to_json(self, extras: Optional[Dict[str, Any]] = None, include_bbox: bool = False, **kwargs):
        """Convert the textblock into a JSON object

        Args:
            extras (Dict[str, Any], optional): Any additional fields that should be included. 
                Defaults to None
            include_bbox (bool, optional): Defaults to False.
            **kwargs: Arbitrary keyword arguments to be pass to superclass

        Returns:
            Dict[str, Any]
        """
        if not extras:
            extras = {}
        extras['type'] = self.type.name.lower()
        extras['block_text'] = self.get_text()
        return super().to_json(**kwargs, extras=extras, include_bbox=include_bbox)

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        if len(self.items) > 0 and len(self.items[0].spans) > 0:
            text = self.items[0].spans[0].text + "..."
        else:
            text = ""
        return super()._str_rep(extras={'type': self.type, 'text': text})
