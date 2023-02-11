from dataclasses import dataclass
from typing import List, Any, Dict, Optional

import unicodedata

@dataclass
class CFont:
    name: str
    family: str
    size: float
    colour: int
    bold: bool
    italic: bool
    superscript: bool

    def __repr__(self):
        return f"<Font {self.name} Family={self.family} Size={self.size} Colour={self.colour} b={self.bold} i={self.italic} s={self.superscript}>"

@dataclass
class CSpan:
    font: CFont
    text: str

    @staticmethod
    def from_dict(s: Any):
        font_family = s['font'].split("-")[0].split("_")[0]
        return CSpan(
            font = CFont(s['font'], font_family, round(s['size'],1), s['color'], s['flags'] & 16 == 16, s['flags'] & 2 == 2, s['flags'] & 1 == 1),
            text = unicodedata.normalize('NFKC', s['text']),
        )

    def to_html(self):
        text = self.text
        if self.font.bold:
            text = "<b>" + text + "</b>"
        if self.font.italic:
            text = "<i>" + text + "</i>"
        return text

    def __repr__(self):
        return f"<Span '{self.text}' Font={self.font}>"



@dataclass
class CParagraph:
    lines: List[List[CSpan]]

    def to_html(self):
        lines = [''.join(s.to_html() for s in line) for line in self.lines]
        return f"<p>{'</br>'.join(lines)}</p>"

    def to_json(self):
        return {'type':'para', 'spans':[[s.to_json() for s in line] for line in self.lines]}

@dataclass
class CTitle:
    id: str
    spans: List[CSpan]
    level: int

    def to_html(self):
        level = max(4-self.level, 1)
        return f"<h{level}>{''.join(s.to_html() for s in self.spans)}</h{level}>"

    def to_json(self):
        return {'type':'title', 'spans':[s.to_json() for s in self.spans], 'level':self.level}

@dataclass
class CTable:
    headers: List[CParagraph]
    values: List[List[CParagraph]]
    caption: CParagraph
    title: CTitle

    def to_html(self):
        text = "<div>"
        if self.title:
            text += self.title.to_html()
        text = "<table>"
        if self.headers and len(self.headers) > 0:
            text += f"<tr><th>{'</th><th>'.join(h.to_html() for h in self.headers)}</th></tr>"
        if self.values and len(self.values) > 0:
            for row in self.values:
                text += f"<tr><td>{'</td><td>'.join(r.to_html() for r in row)}</td></tr>"
        text += "</table>"
        
        if self.caption:
            text += self.caption.to_html()
        text += "</div>"

        return text

@dataclass
class CImage:
    content: Any
    caption: Optional[CParagraph]

    def to_html(self):
        return f"<b>---IMAGE---</b></br>{self.caption.to_html() if self.caption else ''}"

@dataclass
class CListItem:
    label: CSpan
    items: CParagraph

@dataclass
class CTextList:
    ordered: bool
    items: List[CListItem]

@dataclass
class CToCItem:
    level: int
    text: CParagraph
    id_reference: str

@dataclass
class CToC:
    items: List[CToCItem]

@dataclass
class CAside:
    content: List[Any]

    def to_html(self):
        text = "<div style='background:#eeeeee'>"
        text += "</br>".join(c.to_html() for c in self.content)
        text += "</div>"
        return text

@dataclass
class CHeaderFooter:
    paras: List[CParagraph]

    def to_html(self):
        text = "<div><small>"
        text += "</br>".join(p.to_html() for p in self.paras)
        text += "</small></div>"
        return text