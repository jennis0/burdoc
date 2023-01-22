from dataclasses import dataclass
from enum import Enum, auto
import unicodedata
from typing import List, Any, Tuple
from PIL.Image import Image as PILImage
from .bbox import Bbox


@dataclass
class LayoutElement:
    bbox: Bbox


@dataclass
class Font:
    name: str
    family: str
    size: float
    colour: int
    bold: bool
    italic: bool
    superscript: bool

    def __repr__(self):
        return f"<Font {self.name} Size={self.size} Colour={self.colour} b={self.bold} i={self.italic} s={self.superscript}>"

@dataclass
class Span:
    font: Font
    text: str

    @staticmethod
    def from_dict(s: Any):
        font_family = s['font'].split("-")[0].split("_")[0]
        return Span(
            font = Font(s['font'], font_family, s['size'], s['color'], s['flags'] & 16 == 16, s['flags'] & 2 == 2, s['flags'] & 1 == 1),
            text = unicodedata.normalize('NFKC', s['text']),
        )

    def __repr__(self):
        return f"<Span '{self.text}' Font={self.font}>"

@dataclass
class Line:

    class LineType(Enum):
        Text = auto()
        Break = auto()

    type: LineType
    bbox: Bbox
    spans: List[Span]

    @staticmethod
    def from_dict(l: Any):
        return Line(
            type=Line.LineType.Text,
            spans=[Span.from_dict(s) for s in l['spans']],
            bbox=Bbox(*l['bbox'])
        )

    def __repr__(self):
        return f"<Line Type={self.type.name} Bbox={self.bbox}{' Text='+self.spans[0].text if len(self.spans)>0 else ''}>"

@dataclass
class Drawing:
    class DrawingType(Enum):
        Line = auto()
        Rect = auto()
    
    type: DrawingType
    bbox: Bbox
    opacity: float

@dataclass
class Image:

    class ImageType(Enum):
        Invisible=auto() # images that aren't visible on page
        Background=auto() #used as the base page image
        Section=auto() #identifies a section/aside on the page
        Inline=auto() #small image that sits within the flow of text
        Decorative=auto() #decorative image that sits outside the flow of text
        Primary=auto() #a hero image that illustrates the page
        Gradient=auto() #a gradient type image usually non functional
        Line = auto() #a line

    type: ImageType
    bbox: Bbox
    image: PILImage
    properties: Any

@dataclass
class Table:

    bbox: Bbox
    headers: List[str]
    values : List[List[str]]


@dataclass
class Block:

    class BlockType:
        Text = auto()
        Table = auto()
        Image = auto()

    class Alignment(Enum):
        unknown = auto()
        left = auto()
        center = auto()
        right = auto()

    type: BlockType
    bbox: Bbox
    fonts : List[Tuple[str, float]]
    alignment : Alignment
    open : bool
    lineheight: float
    lines: List[Any]=None
    table: Table=None
    image: Image=None

    def __repr__(self) -> str:
        if self.type == Block.BlockType.Text:
            if len(self.lines) > 0:
                if len(self.lines[0].spans) > 0:
                    text = self.lines[0].spans[0].text
                else:
                    text = ""
                return u"<TextBlock '"+text+f"...' Lines="+str(len(self.lines))+u">"
            else:
                return f"<TextBlock Lines=0>"
        elif self.type == Block.BlockType.Table:
            return f"<TableBlock>"
        elif self.type == Block.BlockType.Image:
            return f"<ImageBlock>"

@dataclass
class Section:
    bbox: Bbox
    items: List[Any]
    default: bool
    backing_drawing: Any
    backing_image: Any
    inline: bool=False

