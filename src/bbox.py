from __future__ import annotations
from dataclasses import dataclass
from typing import List, Any


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

    def center(self) -> Point:
        return Point(
            self.x0 + 0.5*(self.x1-self.x0), 
            self.y0 + 0.5*(self.y1-self.y0)
        )

    def width(self) -> float:
        return self.x1 - self.x0

    def height(self) -> float:
        return self.y1 - self.y0

    def is_vertical(self) -> bool:
        return self.height() > self.width()

    def to_rect(self) -> Any:
        return [self.x0, self.y0, self.x1, self.y1]

    def clone(self):
        return Bbox(*self.to_rect())

    def x_overlap(self, b2: Bbox, normalisation: str="") -> float:
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
        if w < 1 and x_overlap > 0:
            return 1
        return x_overlap / w


    def y_overlap(self, b2: Bbox, normalisation: str="") -> float:
        y_overlap = max(min(self.y1, b2.y1) - max(self.y0, b2.y0), 0)
        if normalisation == "":
            h = 1
        if normalisation == "first":
            h = self.height()
        elif normalisation ==  "second":
            h = b2.height()
        elif normalisation == 'min':
            h = min(self.height(), b2.height())
        elif normalisation == 'max':
            h = max(self.height(), b2.height())
        if h < 1 and y_overlap > 0:
            return 1
        return y_overlap / h

    def overlap(self, b2: Bbox, normalisation : str="") -> float:
        return self.x_overlap(b2, normalisation) * self.y_overlap(b2, normalisation)

    def x_distance(self, b2: Bbox) -> float:
        '''Returns positive if b2 is below this Bbox.'''
        return b2.center().x - self.center().x
    
    def y_distance(self, b2: Bbox) -> float:
        '''Returns positive if n2 is to the right of this node.'''
        return b2.center().y - self.center().y

    @staticmethod
    def from_points(p1: Point, p2: Point):
        return Bbox(p1.x, p1.y, p2.x, p2.y)

    @staticmethod
    def merge(bboxes: List[Bbox]) -> Bbox:
        bbox = Bbox(1000, 1000, 0, 0)
        for bb in bboxes:
            bbox.x0 = min(bbox.x0, bb.x0)
            bbox.y0 = min(bbox.y0, bb.y0)
            bbox.x1 = max(bbox.x1, bb.x1)
            bbox.y1 = max(bbox.y1, bb.y1)
        return bbox

    def __repr__(self):
        return f'<Bbox x0={round(self.x0, 2)}, y0={round(self.y0, 2)} x1={round(self.x1, 2)}, y1={round(self.y1, 2)}>'
