from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Dict, Any
from .bbox import Bbox
from .element import LayoutElementGroup
from .layout_objects import LineElement


class TextBlockType(Enum):
    Small = auto()
    Paragraph = auto()
    H1 = auto()
    H2 = auto()
    H3 = auto()
    H4 = auto()
    H5 = auto()
    Emphasis = auto()

class TextBlock(LayoutElementGroup):

    open : bool
    type: TextBlockType

    def __init__(self, 
                 bbox: Optional[Bbox]=None, 
                 items: Optional[List[LineElement]]=None, 
                 open: Optional[bool]=False,
                 variant: TextBlockType=TextBlockType.Paragraph
                 ):
        super().__init__(bbox, items, title="TextBlock")
        self.variant = variant
        self.open = open

    def get_text(self):
        return " ".join(i.get_text() for i in self.items)

    def to_html(self) -> str:
        variant_lookup = {
            TextBlockType.Small: "small",
            TextBlockType.Emphasis: "emphasis",
            TextBlockType.Paragraph:"p",
            TextBlockType.H1:"h1",
            TextBlockType.H2:"h2",
            TextBlockType.H3:"h3",
            TextBlockType.H4:"h4",
            TextBlockType.H5:"h5"
        }
        type = variant_lookup[self.type]
        return f"<{type}>" + "\n".join(l.to_html() for l in self.items) + f"</{type}>"

    def to_json(self, **kwargs) -> Dict[str, Any]:
        return super().to_json(extras={"variant":self.variant.name.lower()}, **kwargs)

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        if len(self.items) > 0 and len(self.items[0].spans) > 0:
            text = self.items[0].spans[0].text + "..."
        else:
            text = ""
        return super()._str_rep(extras={'variant':self.variant, 'text':text})