from __future__ import annotations
from typing import List,Optional
from uuid import uuid4
from .bbox import Bbox


class LayoutElement:
    bbox: Bbox

    def __init__(self, bbox: Bbox, title: Optional[str]=None):
        self.title = title if title else 'LayoutElement'
        self.id = uuid4().hex
        self.bbox = bbox

    def _str_rep(self, extras=None) -> str:
        if extras:
            extra_str = " ".join(f"{t}={extras[t]}" for t in extras)
            if len(extra_str) > 0:
                extra_str = " "+extra_str
        else:
            extra_str = ""
        return f"<{self.title} Id={self.id[8]}... Bbox={self.bbox}{extra_str}>" 

    def __str__(self) -> str:
        return self._str_rep()
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def to_html(self, content=""):
        return f"<div>{content}</div>"
    
    def to_json(self, include_bbox=False, extras=None):
        if not extras:
            extras = {}

        extras['type'] = self.title.lower()
        if include_bbox:
            extras['bbox'] = self.bbox.to_json()

        return extras

class LayoutElementGroup(LayoutElement):
    items: List[LayoutElement]
    open: bool

    def __init__(self, bbox: Optional[Bbox]=None, items: Optional[List[LayoutElement]]=None, open: Optional[bool]=False, title: Optional[str]=None):
        
        if not title:
            title = "LayoutElementGroup"

        if bbox and not items:
            super().__init__(bbox=bbox, title=title)
            self.items = []
        elif items and not bbox:
            super().__init__(bbox=Bbox.merge([line.bbox for line in items]), title=title)
            self.items = items
        elif items and bbox:
            super().__init__(bbox=bbox, title=title)
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
        extras = {"N_Items":len(self.items)}
        return self._str_rep(extras)
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def to_html(self):
        return super().to_html("".join(i.to_html() for i in self.items))
    
    def to_json(self, extras=None, **kwargs):
        if not extras:
            extras = {}
        extras['items'] = [i.to_json() for i in self.items]
        return super().to_json(extras=extras, **kwargs)