from dataclasses import dataclass
from typing import Dict, Any, Tuple

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
    def split_font_name(fontname: str, type: str="") -> Tuple[str, str]:
        """Splits a font into family and base name (family-variation). Optional type argument
        only used when an unnamed font is found.
        
        Consistently handles font subsetting and variations.

        Args:
            fontname (str): Full name of a font
            type (str, optional): Font type. Defaults to "".

        Returns:
            Tuple[str, str]: (font family, font basename)
        """
        if "+" in fontname:
            fontname = fontname.split("+")[1]
                        
        family = fontname.split("-")[0].split("_")[0]
        if family == "":
            family = "Unnamed"
            if type != "":
                fontname = f"Unnamed-T{type[-1]}"
            else:
                fontname = "Unnamed-T?"
                
        return (family, fontname)

    @staticmethod
    def from_dict(span_dict: Dict[str, Any]):
        """Creates Font object from a PyMuPDF span

        Some properties are inferred based on PyMuPDF flags, others are set dynamically from the font name

        Args:
            font_doct (Dict[str, Any]): _description_
        """
        
        family, fontname = Font.split_font_name(span_dict['font'])
        fontparts = fontname.split('-')
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
        smallcaps = any(x in font_modifier for x in ['sc', 'smallcaps', 'caps']) or \
            any(font_family.endswith(x) for x in ['SC', 'SmallCaps']) or \
                any(x in font_family for x in ['Caps'])
                
        return Font(fontname, font_family, round(span_dict['size'], 1), span_dict['color'],
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
