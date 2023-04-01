from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from .bbox import Bbox


class LayoutElement:
    """Base class for any layout object within the PDF. LayoutElements can be used to describe
    anything that has a bbox.
    """

    bbox: Bbox

    def __init__(self, bbox: Bbox, title: str = "LayoutElement"):
        self.title = title
        self.element_id = uuid4().hex
        self.bbox = bbox

    def _str_rep(self, extras=None) -> str:
        if extras:
            extra_str = " ".join(f"{t}={extras[t]}" for t in extras)
            if len(extra_str) > 0:
                extra_str = " "+extra_str
        else:
            extra_str = ""
        return f"<{self.title} Id={self.element_id[:8]}... Bbox={self.bbox}{extra_str}>"

    def __str__(self) -> str:
        return self._str_rep()

    def __repr__(self) -> str:
        return self.__str__()

    def to_json(self, extras: Optional[Dict[str, Any]] = None, include_bbox: bool = False) -> Dict[str, Any]:
        """Convert the object into a JSON object

        Example JSON:
        ::

            {
                "name": "LayoutElement",
                "bbox": {...} [optional]
            }

        Args:
            extras (Optional[Dict[str, Any]], optional): Any additional items that
                should be included within the JSON. Defaults to None.
            include_bbox (bool, optional): Include the bounding box. Defaults to False.

        Returns:
            Dict[str, Any]: A JSON representation of the object.
        """

        if not extras:
            extras = {}

        extras['name'] = self.title.lower()
        if include_bbox:
            extras['bbox'] = self.bbox.to_json()

        return extras


class LayoutElementGroup(LayoutElement):
    """Base class for any coherent group of layout objects within the PDF. The BBox of the 
    LayoutElementGroup is the rectangle encompassing all Bboxes of it's members.
    """

    def __init__(self, bbox: Optional[Bbox] = None,
                 items: Optional[List[LayoutElement]] = None,
                 title: str = "LayoutElementGroup"):

        if bbox and not items:
            super().__init__(bbox=bbox, title=title)
            self.items = []
        elif items and not bbox:
            super().__init__(bbox=Bbox.merge(
                [line.bbox for line in items]), title=title)
            self.items = items
        elif items and bbox:
            super().__init__(bbox=bbox, title=title)
            self.items = items
        else:
            raise TypeError(
                "Require either a bbox or item list to create LayoutElementGroup")

        self._index = 0

    def append(self, item: LayoutElement, update_bbox: bool = True):
        """Add an item to the group

        Args:
            item (LayoutElement): Item to add
            update_bbox (bool, optional): Should the group Bbox be recalculated or ignored?
                Useful when items are non-contigous (e.g. they cross columns or pages).
                Defaults to True.
        """
        self.items.append(item)
        if update_bbox:
            self.bbox = Bbox.merge([self.bbox, item.bbox])

    def remove(self, item: LayoutElement, update_bbox: bool = True):
        """Remove an item from the group

        Args:
            item (LayoutElement): Item to remove
            update_bbox (bool, optional): Should the group Bbox be recalculated or ignored?
                Defaults to True.

        Raises:
            ValueError: Item not present in list
        """
        self.items.remove(item)
        if update_bbox and len(self.items) > 0:
            self.bbox = Bbox.merge([i.bbox for i in self.items])

    def merge(self, leg: LayoutElementGroup) -> LayoutElementGroup:
        """In-place merge with another LayoutElementGroup

        Args:
            leg (LayoutElementGroup): LEG to merge with

        Returns:
            LayoutElementGroup: A reference to self
        """
        self.items += leg.items
        self.items.sort(key=lambda i: round(i.bbox.y0/10, 0)*1000 + i.bbox.x0)
        self.bbox = Bbox.merge([self.bbox, leg.bbox])
        return self

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        if self._index >= len(self.items):
            raise StopIteration()
        self._index += 1
        return self.items[self._index - 1]

    def _str_rep(self, extras=None) -> str:
        if extras:
            extras['N_items'] = len(self.items)
        else:
            extras = {'N_items': len(self.items)}
        return super()._str_rep(extras)

    def __repr__(self) -> str:
        return self.__str__()

    def to_json(self, extras: Optional[Dict[str, Any]] = None, include_bbox: bool = False) -> Dict[str, Any]:
        """Creates JSON object from LayoutElementGroup

        Example JSON:
        ::

                {
                    "name": "LayoutElementGroup",
                    "bbox": {...} [optional]
                    "items": [{...}]
                }

        Args:
            extras (Optional[Dict[str, Any]], optional): Any additional items that
                need to be included in the JSON. Defaults to None.
            include_bbox (bool, optional): Include the bounding box. Defaults to False.

        Returns:
            Dict[str, Any]: A JSON representation of the group
        """
        if not extras:
            extras = {}
        extras['items'] = [i.to_json() for i in self.items]
        return super().to_json(extras=extras, include_bbox=include_bbox)
