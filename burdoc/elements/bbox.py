from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Bbox:
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float

    def x0_norm(self) -> float:
        return self.x0 / self.page_width

    def x1_norm(self) -> float:
        return self.x1 / self.page_width

    def y0_norm(self) -> float:
        return self.y0 / self.page_height

    def y1_norm(self) -> float:
        return self.y1 / self.page_height

    def center(self, norm: bool = False) -> Point:
        if norm:
            return Point(
                (self.x0 + 0.5*(self.x1-self.x0)) / self.page_width, 
                (self.y0 + 0.5*(self.y1-self.y0)) / self.page_height
            )
        else:
            return Point(
                self.x0 + 0.5*(self.x1-self.x0), 
                self.y0 + 0.5*(self.y1-self.y0)
            )

    def width(self, norm: bool = False) -> float:
        if norm:
            return (self.x1 - self.x0) / self.page_width
        else:
            return self.x1 - self.x0

    def height(self, norm: bool = False) -> float:
        if norm:
            return (self.y1 - self.y0) / self.page_height
        else:
            return self.y1 - self.y0

    def is_vertical(self) -> bool:
        return self.height() > self.width()

    def to_rect(self) -> Any:
        return [self.x0, self.y0, self.x1, self.y1]

    def clone(self):
        return Bbox(*self.to_rect(), self.page_width, self.page_height)

    def x_overlap(self, b2: Bbox, normalisation: str = "") -> float:
        x_overlap = max(min(self.x1, b2.x1) - max(self.x0, b2.x0), 0)
        if normalisation == "":
            w = 1
        if normalisation == "first":
            w = self.width()
        elif normalisation ==  "second":
            w = b2.width()
        elif normalisation == 'min':
            w = min(self.width(), b2.width())
        elif normalisation == 'max':
            w = max(self.width(), b2.width())
        elif normalisation == 'page':
            w = self.page_width
        if w < 1 and x_overlap > 0:
            return 1
        return x_overlap / w

    def y_overlap(self, b2: Bbox, normalisation: str = "") -> float:
        y_overlap = max(min(self.y1, b2.y1) - max(self.y0, b2.y0), 0)
        if y_overlap < 0.01:
            return 0
        
        if normalisation == "":
            h = 1
        if normalisation == "first":
            h = self.height()
        elif normalisation == "second":
            h = b2.height()
        elif normalisation == 'min':
            h = min(self.height(), b2.height())
        elif normalisation == 'max':
            h = max(self.height(), b2.height())
        elif normalisation == 'page':
            h = self.page_height

        if h < 1:
            return 1
        
        return y_overlap / h

    def overlap(self, b2: Bbox, normalisation: str = "") -> float:
        return self.x_overlap(b2, normalisation) * \
            self.y_overlap(b2, normalisation)

    def x_distance(self, b2: Bbox) -> float:
        '''Returns positive if b2 is below this Bbox.'''
        return b2.center().x - self.center().x
    
    def y_distance(self, b2: Bbox) -> float:
        '''Returns positive if n2 is to the right of this node.'''
        return b2.center().y - self.center().y

    @staticmethod
    def from_points(p1: Point, p2: Point, page_width: float, page_height: float):
        return Bbox(p1.x, p1.y, p2.x, p2.y, page_width, page_height)

    @staticmethod
    def merge(bboxes: List[Bbox]) -> Bbox:
        bbox = Bbox(1000, 1000, 0, 0, bboxes[0].page_width, bboxes[0].page_height)
        for bb in bboxes:
            bbox.x0 = min(bbox.x0, bb.x0)
            bbox.y0 = min(bbox.y0, bb.y0)
            bbox.x1 = max(bbox.x1, bb.x1)
            bbox.y1 = max(bbox.y1, bb.y1)
        return bbox

    def to_json(self, include_page=False):
        if not include_page:
            return {'x0':self.x0, 'y0':self.y0, 'x1':self.x1, 'y1':self.y1}
        else:
            return {'x0':self.x0, 'y0':self.y0, 'x1':self.x1, 'y1':self.y1, 
                    'pw':self.page_width, 'ph':self.page_height}

    def __repr__(self):
        return f'<Bbox x0={round(self.x0, 2)}, y0={round(self.y0, 2)} x1={round(self.x1, 2)}, y1={round(self.y1, 2)} w={round(self.page_width, 2)}, h={round(self.page_height, 2)}>'
