from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Bbox:
    """Utility class for storing and manipulating bounding boxes.
    """
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float

    def x0_norm(self) -> float:
        """x0 normalised by its position on the page

        Returns:
            float
        """
        return self.x0 / self.page_width

    def x1_norm(self) -> float:
        """x1 normalised by its position on the page

        Returns:
            float
        """
        return self.x1 / self.page_width

    def y0_norm(self) -> float:
        """y0 normalised by its position on the page

        Returns:
            float
        """
        return self.y0 / self.page_height

    def y1_norm(self) -> float:
        """y1 normalised by its position on the page

        Returns:
            float
        """
        return self.y1 / self.page_height

    def area(self) -> float:
        """Returns total area of bbox

        Returns:
            float
        """
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def area_norm(self) -> float:
        """Returns total area of bbox as a percentage of the 
        page area.

        Returns:
            float
        """
        return self.area() / (self.page_height*self.page_width)

    def center(self, norm: bool = False) -> Point:
        """Returns a point representing the center of the bounding
        box.

        Args:
            norm (bool, optional): Return page-normalised co-ordinates.
            Defaults to False.

        Returns:
            Point
        """
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
        """Returns the width of the bounding box.

        Args:
            norm (bool, optional): Return page-normalised co-ordinates.
            Defaults to False.

        Returns:
            float
        """
        if norm:
            return (self.x1 - self.x0) / self.page_width
        else:
            return self.x1 - self.x0

    def height(self, norm: bool = False) -> float:
        """Returns the height of the bounding box.

        Args:
            norm (bool, optional): Return page-normalised co-ordinates.
            Defaults to False.

        Returns:
            float
        """
        if norm:
            return (self.y1 - self.y0) / self.page_height
        else:
            return self.y1 - self.y0

    def is_vertical(self) -> bool:
        """Test if the Bounding box is oriented vertically.
        I.e. that the height is greater than the width.

        Returns:
            bool: _description_
        """
        return self.height() > self.width()

    def to_rect(self) -> List[float]:
        """Returns a four point representation of the box.

        Returns:
            List[float]: [x0, y0, x1, y1]
        """
        return [self.x0, self.y0, self.x1, self.y1]

    def clone(self) -> Bbox:
        """Returns a clone of the bounding box

        Returns:
            Bbox
        """
        return Bbox(*self.to_rect(), self.page_width, self.page_height)  # type:ignore

    def x_overlap(self, other_bbox: Bbox, normalisation: str = "") -> float:
        """Calculates the projected overlap between this Bbox and another in the x
        axis. Several normalisation options are provided:

        "": No normalisation
        "first": Return as percent of calling bounding box width
        "second": Return as percent of passed bounding box width
        "min": Return as percent of thinnest box width
        "max": Return as percent of widest box width
        "page": Return as percent of page width

        Args:
            other_bbox (Bbox): Passed bbox
            normalisation (str, optional): Normalisation option. Defaults to "".

        Returns:
            float
        """
        x_overlap = max(min(self.x1, other_bbox.x1) -
                        max(self.x0, other_bbox.x0), 0)
        if x_overlap < 0.01:
            return 0.

        if normalisation == "":
            width = 1.
        if normalisation == "first":
            width = self.width()
        elif normalisation == "second":
            width = other_bbox.width()
        elif normalisation == 'min':
            width = min(self.width(), other_bbox.width())
        elif normalisation == 'max':
            width = max(self.width(), other_bbox.width())
        elif normalisation == 'page':
            width = self.page_width
        if width < 1 and x_overlap > 0:
            return 1.
        return x_overlap / width

    def y_overlap(self, other_bbox: Bbox, normalisation: str = "") -> float:
        """Calculates the projected overlap between this Bbox and another in the y
        axis. Several normalisation options are provided:

        "": No normalisation
        "first": Return as percent of calling bounding box height
        "second": Return as percent of passed bounding box height
        "min": Return as percent of shortest box height
        "max": Return as percent of tallest box height
        "page": Return as percent of page height

        Args:
            other_bbox (Bbox): Passed bbox
            normalisation (str, optional): Normalisation option. Defaults to "".

        Returns:
            float
        """
        y_overlap = max(min(self.y1, other_bbox.y1) -
                        max(self.y0, other_bbox.y0), 0)
        if y_overlap < 0.01:
            return 0.

        if normalisation == "":
            height = 1.
        if normalisation == "first":
            height = self.height()
        elif normalisation == "second":
            height = other_bbox.height()
        elif normalisation == 'min':
            height = min(self.height(), other_bbox.height())
        elif normalisation == 'max':
            height = max(self.height(), other_bbox.height())
        elif normalisation == 'page':
            height = self.page_height

        if height < 1:
            return 1.

        return y_overlap / height

    def overlap(self, other_bbox: Bbox, normalisation: str = "") -> float:
        """Calculates the overall overlap between this Bbox and another. 
        Several normalisation options are provided:

        "": No normalisation
        "first": Return as percent of calling bounding box area
        "second": Return as percent of passed bounding box area
        "min": Return as percent of smallest area
        "max": Return as percent of largest area
        "page": Return as percent of page area

        Args:
            other_bbox (Bbox): Passed bbox
            normalisation (str, optional): Normalisation option. Defaults to "".

        Returns:
            float
        """
        if normalisation == 'min':
            normalisation = 'first' if self.area() < other_bbox.area() else 'second'
        elif normalisation == 'max':
            normalisation = 'first' if self.area() > other_bbox.area() else 'second'

        return self.x_overlap(other_bbox, normalisation) * \
            self.y_overlap(other_bbox, normalisation)

    def x_distance(self, other_bbox: Bbox) -> float:
        """Returns the distance between called and passed Bbox in the x direction.
        Note that this is calculated centre to centre. It returns negatively if passed Bbox is below 
        this Bbox.

        Args:
            other_bbox (Bbox)

        Returns:
            float
        """
        return other_bbox.center().x - self.center().x

    def y_distance(self, other_bbox: Bbox) -> float:
        """Returns the distance between called and passed Bbox in the y direction.
        Note that this is calculated centre to centre. It returns negatively if passed Bbox is to the
        right of this Bbox.

        Args:
            other_bbox (Bbox)

        Returns:
            float
        """
        return other_bbox.center().y - self.center().y

    @staticmethod
    def from_points(p1: Point, p2: Point, page_width: float, page_height: float) -> Bbox:
        """Create a Bbox spanning two points. 

        Args:
            p1 (Point): Top-left corner
            p2 (Point): Bottom-right corner
            page_width (float): Width of page
            page_height (float): Height of page

        Returns:
            Bbox
        """
        return Bbox(p1.x, p1.y, p2.x, p2.y, page_width, page_height)

    @staticmethod
    def merge(bboxes: List[Bbox]) -> Bbox:
        """Merge several Bboxes into a single bbox spanning all of them

        Args:
            bboxes (List[Bbox])

        Raises:
            ValueError: No bboxes passed

        Returns:
            Bbox
        """
        if len(bboxes) == 0:
            raise ValueError("At least one bbox required")

        bbox = Bbox(1000, 1000, 0, 0,
                    bboxes[0].page_width, bboxes[0].page_height)
        for bb in bboxes:
            bbox.x0 = min(bbox.x0, bb.x0)
            bbox.y0 = min(bbox.y0, bb.y0)
            bbox.x1 = max(bbox.x1, bb.x1)
            bbox.y1 = max(bbox.y1, bb.y1)
        return bbox

    def to_json(self, include_page=False) -> Dict[str, float]:
        """Convert a Bbox to JSON format.

        Example:

        ::

                {
                    'x0':float, 
                    'y0':float, 
                    'x1':float, 
                    'y1':float,
                    'pw':float [optional], 
                    'ph':float [optional]
                }

        Args:
            include_page (bool, optional): Include page width and height. 
                Defaults to False.

        Returns:
            Dict[str, float]
        """
        if not include_page:
            return {'x0': round(self.x0, 4), 'y0': round(self.y0, 4), 'x1': round(self.x1, 4), 'y1': round(self.y1, 4)}
        else:
            return {'x0': round(self.x0, 4), 'y0': round(self.y0, 4), 'x1': round(self.x1, 4), 'y1': round(self.y1, 4),
                    'pw': round(self.page_width, 4), 'ph': round(self.page_height, 4)}

    def __repr__(self):
        return f'<Bbox x0={round(self.x0, 2)}, y0={round(self.y0, 2)} x1={round(self.x1, 2)}, y1={round(self.y1, 2)} w={round(self.page_width, 2)}, h={round(self.page_height, 2)}>'
