from dataclasses import dataclass
from typing import List, Any, Dict, Optional

from .textblock import TextBlock
from .span import Span
from .bbox import Bbox
from .layout_objects import LineElement
from .element import LayoutElementGroup, LayoutElement


class Paragraph(LayoutElementGroup):
    
    def to_html(self):
        lines = [''.join(s.to_html() for s in line) for line in self.lines]
        return f"<p>{'</br>'.join(lines)}</p>"

    def to_json(self):
        return {'type':'para', 'spans':[[s.to_json() for s in line] for line in self.lines]}


class Column(LayoutElementGroup):

    def __init__(self, bbox: Optional[Bbox] = None, items: Optional[List[LayoutElementGroup]] = None, open: Optional[bool] = False):
        super().__init__(bbox, items, open)
    
    def __str__(self) -> str:
        if len(self.items) > 0:
            text = self.items[0].to_html() + "..."
        else:
            text = ""
        return u"<Column Id="+self.id[:8]+u"... Text='"+text+u"' Bbox="+str(self.bbox)+u" N_Items="+str(len(self.items))+u">"
    

class Title(TextBlock):
    level: int
    
    def to_html(self):
        level = max(4-self.level, 1)
        return f"<h{level}>{''.join(s.to_html() for s in self.items)}</h{level}>"

    def to_json(self):
        return {'type':'title', 'spans':[s.to_json() for s in self.items], 'level':self.level}

@dataclass
class ListItem:
    label: Span
    items: Paragraph

@dataclass
class TextList:
    ordered: bool
    items: List[ListItem]

@dataclass
class TableOfContentItem:
    level: int
    text: Paragraph
    id_reference: str

@dataclass
class TableOfContent:
    items: List[TableOfContentItem]

@dataclass
class Aside:
    content: List[LayoutElement]

    def to_html(self):
        text = "<div style='background:#eeeeee'>"
        text += "</br>".join(c.to_html() for c in self.content)
        text += "</div>"
        return text

@dataclass
class CHeaderFooter:
    paras: List[Paragraph]

    def to_html(self):
        text = "<div><small>"
        text += "</br>".join(p.to_html() for p in self.paras)
        text += "</small></div>"
        return text