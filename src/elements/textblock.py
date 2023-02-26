from dataclasses import dataclass
from typing import List, Optional
from .bbox import Bbox
from .element import LayoutElementGroup
from .layout_objects import LineElement


@dataclass
class TextBlock(LayoutElementGroup):
    open : bool

    def __init__(self, 
                 bbox: Optional[Bbox]=None, 
                 items: Optional[List[LineElement]]=None, 
                 open: Optional[bool]=False
                 ):
        super().__init__(bbox, items)
        self.open = open

    def get_text(self):
        return " ".join(i.get_text() for i in self.items)

    def to_html(self) -> str:
        return "<p>" + "\n".join(l.to_html() for l in self.items) + "</p>"

    def __str__(self) -> str:
        if len(self.items) > 0 and len(self.items[0].spans) > 0:
            text = self.items[0].spans[0].text + "..."
        else:
            text = ""
        return u"<TextBlock Id="+self.id[:8]+u"... Text='"+text+u"' Bbox="+str(self.bbox)+u" N_Items="+str(len(self.items))+u">"