from typing import Any, Dict, List, Optional

from .bbox import Bbox
from .element import LayoutElement, LayoutElementGroup
from .drawing import DrawingElement
from .image import ImageElement


class PageSection(LayoutElementGroup):
    """A fully contained section of the page on which layout analysis should be
    done independently.
    """

    def __init__(self, bbox: Optional[Bbox] = None, items: Optional[List[LayoutElement]] = None, default: bool = False,
                 backing_drawing: Optional[DrawingElement] = None, backing_image: Optional[ImageElement] = None, inline: bool = False):
        """Create a PageSection. One of bbox or items must be provided

        Args:
            bbox (Optional[Bbox], optional): BBox of the section. Defaults to None.
            items (Optional[List[LayoutElement]], optional): Items contained within the section. 
                Defaults to None.
            default (bool, optional): Is this part of the underlying page or a subsection. 
                Defaults to False.
            backing_drawing (Optional[Any], optional): Drawing used as the background for this
                section only. Defaults to None.
            backing_image (Optional[Any], optional): Image used as the background for this section
                only. Defaults to None.
            inline (bool, optional): Is this section inline with surrounding text. Usually
                inferred later in the pipeline. Defaults to False.
        """
        super().__init__(bbox=bbox, items=items, title="PageSection")
        self.default = default
        self.backing_drawing = backing_drawing
        self.backing_image = backing_image
        self.inline = inline

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        extras = {'Default': self.default, 'Backing': (
            self.backing_drawing or self.backing_image)}
        return super()._str_rep(extras)

    def to_json(self, extras: Optional[Dict] = None, include_bbox: bool = False, **kwargs):
        if not extras:
            extras = {}
        if self.backing_drawing:
            extras['backing'] = self.backing_drawing.to_json(
                include_bbox=False)
        if self.backing_image:
            extras['backing'] = self.backing_image.to_json(include_bbox=False)

        extras['inline'] = self.inline
        extras['default'] = self.default
        return super().to_json(extras=extras, include_bbox=include_bbox, **kwargs)
