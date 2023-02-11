from dataclasses import dataclass
from enum import Enum, auto
import unicodedata
from typing import List, Any, Tuple
from PIL.Image import Image as PILImage
from .bbox import Bbox

from .content_objects import CSpan, CFont


@dataclass
class LayoutElement:
    bbox: Bbox


@dataclass
class LLine:

    class LineType(Enum):
        Text = auto()
        Break = auto()

    type: LineType
    bbox: Bbox
    spans: List[CSpan]

    def to_html(self):
        return " ".join(s.to_html() for s in self.spans)

    @staticmethod
    def from_dict(l: Any, page_width, page_height):
        return LLine(
            type=LLine.LineType.Text,
            spans=[CSpan.from_dict(s) for s in l['spans']],
            bbox=Bbox(*l['bbox'], page_width, page_height)
        )

    def get_text(self):
        if self.type == LLine.LineType.Text and len(self.spans) > 0:
            return "".join([s.text for s in self.spans])
        return ""

    def __repr__(self):
        return f"<Line Type={self.type.name} Bbox={self.bbox}{' Text='+self.spans[0].text if len(self.spans)>0 else ''}>"

@dataclass
class LDrawing:
    class DrawingType(Enum):
        Line = auto()
        Rect = auto()
    
    type: DrawingType
    bbox: Bbox
    opacity: float

    def to_html(self):
        return "---Drawing---"

@dataclass
class LImage:

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
    bbox: Bbox #Bbox of cropped region containing non-zero content
    original_bbox: Bbox #Bbox representing true size
    image: PILImage
    properties: Any
    inline: bool = False

    def to_html(self):
        return "---Image---"

@dataclass
class LTable:

    bbox: Bbox
    headers: List[LLine]
    values : List[List[List[LLine]]]

    def to_html(self):
        return "---Table---"

    def __str__(self):
        return f"<Table {str(self.bbox)}>"


@dataclass
class LBlock:

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
    table: LTable=None
    image: LImage=None

    def to_html(self) -> str:
        return "<p>" + "\n".join(l.to_html() for l in self.lines) + "</p>"

    def __repr__(self) -> str:
        if self.type == LBlock.BlockType.Text:
            if len(self.lines) > 0:
                if len(self.lines[0].spans) > 0:
                    text = self.lines[0].spans[0].text
                else:
                    text = ""
                return u"<TextBlock '"+text+f"...' Lines="+str(len(self.lines))+u">"
            else:
                return f"<TextBlock Lines=0>"
        elif self.type == LBlock.BlockType.Table:
            return f"<TableBlock>"
        elif self.type == LBlock.BlockType.Image:
            return f"<ImageBlock>"

@dataclass
class LSection:
    bbox: Bbox
    items: List[LayoutElement]
    default: bool=False
    backing_drawing: Any=None
    backing_image: Any=None
    inline: bool=False

    def to_html(self):
        return "</br>".join(i.to_html() for i in self.items)

    def __str__(self):
        return f"<Section {self.bbox} {self.items[0]} {self.default}>"

