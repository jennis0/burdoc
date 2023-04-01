from enum import Enum, auto
from typing import Any, Dict, Optional

from .bbox import Bbox
from .element import LayoutElement


class ImageType(Enum):
    """Enumeration of types of images Burdoc understands.

    - INVISIBLE: Image isn't visible on page  
    - BACKGROUND: Image is used as background for the whole page  
    - SECTION: Image is used as a background for a page section or aside  
    - INLINE: Image is part of the flow of text (currently unused)  
    - DECORATIVE: Image is a decorative element in the page layout but 
      has no semantic meaning  
    - PRIMARY: Image is a 'hero' image on the page  
    - GRADIENT: Image is a smooth gradient used as a background  
    - LINE: Image is used to semantically separate page sections  
    """
    INVISIBLE = auto()  # images that aren't visible on page
    BACKGROUND = auto()  # used as the base page image
    SECTION = auto()  # identifies a section/aside on the page
    INLINE = auto()  # small image that sits within the flow of text
    DECORATIVE = auto()  # decorative image that sits outside the flow of text
    PRIMARY = auto()  # a hero image that illustrates the page
    GRADIENT = auto()  # a gradient type image usually non functional
    LINE = auto()  # a line
    UNKNOWN = auto()  # unknown type


class ImageElement(LayoutElement):
    """Core element representing an image with a page layout
    """

    def __init__(self, bbox: Bbox, original_bbox: Bbox,
                 image: int, properties: Dict[str, Any],
                 image_type: ImageType = ImageType.UNKNOWN,
                 inline: bool = False):
        """Create an image element.

        Args:
            bbox (Bbox): A Bbox representing the image's visible extent
            original_bbox (Bbox): A Bbox representing the image's true extent
            image (int): Index of page image store where image is found
            properties (Dict[str, Any]): Any additional properties of the image
            image_type (ImageType, optional): Purpose of the image. Default is UNKNOWN
            inline (bool, optional): Whether the image layout should be inline or additional. 
                Generally set later in processing. Defaults to False.
                
        """
        super().__init__(bbox, title="Image")
        self.original_bbox = original_bbox
        self.type = image_type
        self.image = image
        self.properties = properties
        self.inline = inline

    def __str__(self):
        extras = {"Type": self.type.name.lower() if self.type else 'none',
                  "Image": self.image}
        return self._str_rep(extras)

    def to_json(self, extras: Optional[Dict] = None, include_bbox: bool = False, **kwargs):
        extras = {'image_type': self.type.name.lower(
        ) if self.type else 'none', 'image': self.image}
        return super().to_json(extras=extras, include_bbox=include_bbox, **kwargs)