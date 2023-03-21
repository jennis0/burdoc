from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Any
from PIL.Image import Image as PILImage

from .span import Span
from .bbox import Bbox
from .element import LayoutElement

class LineElement(LayoutElement):

    bbox: Bbox
    spans: List[Span]

    def __init__(self, bbox: Bbox, spans: List[Span]):
        super().__init__(bbox, title="Line")
        self.spans = spans

    def to_html(self):
        return " ".join(s.to_html() for s in self.spans)

    @staticmethod
    def from_dict(l: Any, page_width, page_height):
        return LineElement(
            spans=[Span.from_dict(s) for s in l['spans']],
            bbox=Bbox(*l['bbox'], page_width, page_height)
        )

    def get_text(self):
        if len(self.spans) > 0:
            return "".join([s.text for s in self.spans])
        return ""

    def __str__(self):
        extras ={"Text":self.spans[0].text if len(self.spans)>0 else ''}
        return self._str_rep(extras)
    
    def to_json(self, **kwargs):
        extras = {'spans': [s.to_json() for s in self.spans]}
        return super().to_json(extras=extras, **kwargs)

@dataclass
class DrawingElement(LayoutElement):
    class DrawingType(Enum):
        Line = auto()
        Rect = auto()
    
    type: DrawingType
    bbox: Bbox
    opacity: float

    def __init__(self, bbox: Bbox, type: DrawingType, opacity: float):
        super().__init__(bbox, title="Drawing")
        self.type = type
        self.opacity = opacity

    def to_html(self):
        return ""
    
    def __str__(self):
        extras={"Type":self.type.name}
        return self._str_rep(extras)
    
    def to_json(self, **kwargs):
        extras = {'type':self.type.name.lower(), 'opacity':self.opacity}
        return super().to_json(**kwargs, extras=extras, include_bbox=True)
    

@dataclass
class ImageElement(LayoutElement):

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
    original_bbox: Bbox #Bbox representing true size
    image: PILImage
    properties: Any
    inline: bool = False

    def __init__(self, bbox: Bbox, original_bbox: Bbox, type: ImageType, 
                 image: PILImage, properties: Any, inline: bool=False):
        super().__init__(bbox, title="Image")
        self.original_bbox = original_bbox
        self.type = type
        self.image = image
        self.properties = properties
        self.inline = inline

    def to_html(self):
        return "---Image---"
    
    def __str__(self):
        extras = {"Type":self.type.name, "Image":self.image}
        return self._str_rep(extras)
    
    def to_json(self, **kwargs):
        extras = {'image_type':self.type.name.lower(), 'image':None}#self.image}
        return super().to_json(extras=extras, **kwargs)


