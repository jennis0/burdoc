from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Font:
    """Representation of font information"""
    
    name: str
    family: str
    size: float
    colour: int
    bold: bool
    italic: bool
    superscript: bool
    smallcaps: bool

    @staticmethod
    def from_dict(span_dict: Dict[str, Any]):
        """Creates Font object from a PyMuPDF span

        Some properties are inferred based on PyMuPDF flags, others are set dynamically from the font name

        Args:
            font_doct (Dict[str, Any]): _description_
        """
        fontparts = span_dict['font'].split('-')
        font_family = fontparts[0]
        
        if len(fontparts) > 1:
            font_modifier = "-".join([p.lower() for p in fontparts[1:]])
        else:
            font_modifier = ""

        bold = (span_dict['flags'] & 16) > 0 or any(
            x in font_modifier for x in ['bold', 'bd'])
        italic = (span_dict['flags'] & 2) > 0 or any(
            x in font_modifier for x in ['italic', 'it'])
        superscript = (span_dict['flags'] & 1) > 0
        smallcaps = any(x in font_modifier for x in ['sc', 'smallcaps']) or font_family.endswith('SC')

        return Font(span_dict['font'], font_family, round(span_dict['size'], 1), span_dict['color'],
                    bold, italic, superscript, smallcaps)

    def __repr__(self):
        return f"<Font {self.name} Family={self.family} Size={float(self.size)} "+\
            f"Colour={self.colour} bd={self.bold} it={self.italic} sp={self.superscript} sc={self.smallcaps}>"

    def to_json(self):
        """Convert the Font into a JSON object

        Returns:
            Dict[str, Any]: A JSON representation of the font.
        """
        return {'name': 'font', 'font': self.name, 'family': self.family, 'size': self.size,
                'colour': self.colour, 'bd': self.bold, 'it': self.italic, 'sp': self.superscript,
                'sc': self.smallcaps
                }
