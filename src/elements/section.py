from typing import List, Any

from .bbox import Bbox
from .element import LayoutElementGroup, LayoutElement

class PageSection(LayoutElementGroup):
    default: bool=False
    backing_drawing: Any=None
    backing_image: Any=None
    inline: bool=False

    def __init__(self, bbox: Bbox, items: List[LayoutElement], default: bool=False, 
                 backing_drawing: Any=None, backing_image: Any=None, inline: bool=False):
        super().__init__(bbox, items)
        self.default = default
        self.backing_drawing = backing_drawing
        self.backing_image = backing_image
        self.inline = inline

    def to_html(self):
        return "</br>".join(i.to_html() for i in self.items)

    def __str__(self):
        return f"<Section Id={self.id[:8]}... Bbox={self.bbox} N_Items={self.items[0]} Default={self.default}>"
