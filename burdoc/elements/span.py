import unicodedata
from dataclasses import dataclass
from typing import Any

from .font import Font


@dataclass
class Span:
    font: Font
    text: str

    @staticmethod
    def from_dict(s: Any):
        font_family = s['font'].split("-")[0].split("_")[0]
        return Span(
            font = Font(s['font'], font_family, round(s['size'],1), str(s['color']), s['flags'] & 16 == 16, s['flags'] & 2 == 2, s['flags'] & 1 == 1),
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
    
    def to_json(self):
        return {'type':'span', 'text':self.text, 'font':self.font.to_json()}