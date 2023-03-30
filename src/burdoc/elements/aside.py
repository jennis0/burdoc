from typing import List, Optional

from .bbox import Bbox
from .element import LayoutElement, LayoutElementGroup


class Aside (LayoutElementGroup):
    """A small delimited section of text that is separate from the surrounding
    flow.
    """

    def __init__(self,
                 bbox: Optional[Bbox] = None,
                 items: Optional[List[LayoutElement]] = None
                 ):
        super().__init__(bbox, items, title="Aside")
