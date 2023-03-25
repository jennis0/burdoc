from typing import Any, List, Optional

from .bbox import Bbox
from .element import LayoutElement, LayoutElementGroup


class PageSection(LayoutElementGroup):
    default: bool=False
    backing_drawing: Any=None
    backing_image: Any=None
    inline: bool=False

    def __init__(self, bbox: Optional[Bbox]=None, items: Optional[List[LayoutElement]]=None, default: Optional[bool]=False, 
                 backing_drawing: Optional[Any]=None, backing_image: Optional[Any]=None, inline: Optional[bool]=False):
        super().__init__(bbox=bbox, items=items, title="PageSection")
        self.default = default
        self.backing_drawing = backing_drawing
        self.backing_image = backing_image
        self.inline = inline

    def to_html(self):
        return "</br>".join(i.to_html() for i in self.items)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        extras = {'Default': self.default, 'Backing':(self.backing_drawing or self.backing_image)}
        return super()._str_rep(extras)
