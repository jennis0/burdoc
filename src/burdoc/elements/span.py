import unicodedata
from dataclasses import dataclass
from typing import Any, Dict

from .font import Font


@dataclass
class Span:
    """Representation of a continuous run of text with the same
    font information.
    """
    font: Font
    text: str

    @staticmethod
    def from_dict(span_dict: Dict[str, Any]):
        """Creates a Span from a PyMuPDF spac dictionary

        Args:
            span_dict (Dict[str, Any])

        Returns:
            Span
        """
        font_family = span_dict['font'].split("-")[0].split("_")[0]
        return Span(
            font=Font(span_dict['font'], font_family, round(span_dict['size'], 1), span_dict['color'],
                      span_dict['flags'] & 16 == 16, span_dict['flags'] & 2 == 2, span_dict['flags'] & 1 == 1),
            text=unicodedata.normalize('NFKC', span_dict['text']),
        )

    def __repr__(self):
        return f"<Span '{self.text}' Font={self.font}>"

    def to_json(self):
        """Convert the Span into a JSON object

        Returns:
            Dict[str, Any]: A JSON representation of the span.
        """
        return {'name': 'span', 'text': self.text, 'font': self.font.to_json()}
