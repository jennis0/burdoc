from typing import Dict, List, Optional

from .bbox import Bbox
from .element import LayoutElement, LayoutElementGroup
from .textblock import TextBlock


class TextListItem (LayoutElementGroup):
    """A single item within a list. Equivalent to <li> """
    label: str
    items: List[TextBlock]  # type:ignore

    def __init__(self, label: str, items: List[TextBlock]):
        """Create a text list item

        Args:
            label (str): The label of the list item. Can be bullet or alphanumeric
            items (List[TextBlock]): The content of the list item
        """

        super().__init__(items=items, title="TextListItem")  # type:ignore
        self.label = label

    def to_json(self, extras: Optional[Dict] = None, include_bbox: bool = False, **kwargs):
        if not extras:
            extras = {}
        extras['label'] = self.label
        return super().to_json(extras=extras, include_bbox=include_bbox, **kwargs)


class TextList (LayoutElementGroup):
    """An ordered or unordered list"""
    ordered: bool
    items: List[TextListItem]  # type:ignore

    def __init__(self, ordered: bool, bbox: Optional[Bbox] = None, items: Optional[List[LayoutElement]] = None):
        """Create a text list. Must provide one of bbox or items. If items are provided
        the bbox will be inferred.

        Args:
            ordered (bool): Is the list ordered (alphanumeric) or unordered (bullets)
            bbox (Optional[Bbox], optional): Bbox containing the list. Defaults to None.
            items (Optional[List[LayoutElement]], optional): Items making up the list. 
                Defaults to None.
        """
        super().__init__(bbox=bbox, items=items, title="TextList")
        self.ordered = ordered

    def to_json(self, extras: Optional[Dict] = None, include_bbox: bool = False, **kwargs):
        if not extras:
            extras = {}
        extras['ordered'] = self.ordered
        return super().to_json(extras=extras, include_bbox=include_bbox, **kwargs)
