from typing import List, Optional

from .bbox import Bbox
from .element import LayoutElement, LayoutElementGroup
from .textblock import TextBlock


class TextListItem (LayoutElementGroup):
    label: str
    items: List[TextBlock]

    def __init__(self, label, items):
        super().__init__(items=items, title="TextListItem")
        self.label = label

    def to_json(self, **kwargs):
        extras = {'label':self.label}
        return super().to_json(extras=extras, **kwargs)

        
class TextList (LayoutElementGroup):
    ordered: bool
    items: List[TextListItem]

    def __init__(self, ordered: bool, bbox: Optional[Bbox] = None, items: Optional[List[LayoutElement]] = None):
        super().__init__(bbox=bbox, items=items, open=False, title="TextList")
        self.ordered = ordered

    def to_json(self, **kwargs):
        extras = {'ordered':self.ordered}
        return super().to_json(extras=extras, **kwargs)


class Aside (LayoutElementGroup):
    def __init__(self, 
                 bbox: Optional[Bbox] = None, 
                 items: Optional[List[LayoutElement]] = None, 
                  ):
        super().__init__(bbox, items, open, title="Aside")

    def to_html(self):
        text = "<div style='background:#eeeeee'>"
        text += "</br>".join(c.to_html() for c in self.items)
        text += "</div>"
        return text