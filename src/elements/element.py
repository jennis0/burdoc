from __future__ import annotations
from typing import List,Optional
from uuid import uuid4
from .bbox import Bbox


class LayoutElement:
    bbox: Bbox

    def __init__(self, bbox: Bbox):
        self.id = uuid4().hex
        self.bbox = bbox
        self.properties = {}

    def __str__(self) -> str:
        return f"<LayoutElement Id={self.id[:8]}... Bbox={self.bbox}>"

class LayoutElementGroup(LayoutElement):
    items: List[LayoutElement]
    open: bool

    def __init__(self, bbox: Optional[Bbox]=None, items: Optional[List[LayoutElement]]=None, open: Optional[bool]=False):
        
        if bbox and not items:
            super().__init__(bbox)
            self.items = []
        elif items and not bbox:
            super().__init__(Bbox.merge([line.bbox for line in items]))
            self.items = items
        elif items and bbox:
            super().__init__(bbox)
            self.items = items
        else:
            raise Exception("Require either a bbox or item list to create LayoutElementGroup")
        
        self._index = 0
        self.open = open

    def append(self, item: LayoutElement, update_bbox: bool=True):
        self.items.append(item)
        if update_bbox:
            self.bbox = Bbox.merge([self.bbox, item.bbox])

    def remove(self, item: LayoutElement, update_bbox: bool=True):
        self.items.remove(item)
        if update_bbox:
            self.bbox = Bbox.merge([i.bbox for i in self.items])

    def merge(self, leg: LayoutElementGroup):
        self.items += leg.items
        self.items.sort(key=lambda i: round(i.bbox.y0/10,0)*1000 + i.bbox.x0)
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

    def __str__(self) -> str:
        return f"<LayoutElementGroup Id={self.id[:8]}... Bbox={self.bbox} N_Items={len(self.items)}>"