import logging
from typing import Any, Dict, List

import fitz
import numpy as np

from ...elements import Bbox, DrawingElement, DrawingType
from ...utils.logging import get_logger


class DrawingHandler():
    """Extracts drawings from a PDF and applies standardisation and basic type inference"""

    def __init__(self, pdf: fitz.Document, log_level: int = logging.INFO):
        self.logger = get_logger('drawing-handler', log_level=log_level)
        self.page_bbox: Bbox = None  # type:ignore
        self.page: fitz.Page = None  # type:ignore
        self.pdf: fitz.Document = pdf
        self.merge_rects = True

    def _is_filled_rect(self, shape_info: Dict[str, Any], page_colour: np.ndarray) -> bool:
        """Check whether shape is filled with a colour distinct from the page background

        Args:
            shape_info (Dict[str, Any]): A PyMuPDF shape dictionary
            page_colour (np.ndarray): An (r,g,b) array representing the primary page colour

        Returns:
            bool: True if this looks like a filled rectangle, False if it is not likely to be visible
        """

        if 'fill_opacity' not in shape_info or shape_info['fill_opacity'] < 0.1:
            return False

        if np.linalg.norm(255.*np.array(shape_info['fill']) - page_colour) < 10:
            return False

        return True

    def _is_stroked_rect(self, shape_info: Dict[str, Any], page_colour: np.ndarray) -> bool:
        """Check whether shape outline is a colour distinct from the page background

        Args:
            shape_info (Dict[str, Any]): A PyMuPDF shape dictionary
            page_colour (np.ndarray): An (r,g,b) array representing the primary page colour

        Returns:
            bool: True if this looks like a filled rectangle, False if it is not likely to be visible
        """

        if 'stroke_opacity' not in shape_info or shape_info['stroke_opacity'] < 0.1:
            return False

        if 'width' not in shape_info or shape_info['width'] < 0.05:
            return False

        if 'color' not in shape_info or np.linalg.norm(np.array(shape_info['color']) - page_colour) < 10:
            return False

        return True

    def _is_bullet(self, drawing_dict: Dict[str, Any]) -> bool:
        """Classifies a drawing as a bullet - looks for a filled item that is small
        and symmetrical.

        Args:
            drawing_dict (Dict[str, Any]): PyMuPDF Drawing dictionary
        Returns:
            bool: Whether or not it is a bullet
        """
        if drawing_dict['type'] == 'f' and drawing_dict['fill_opacity'] > 0.9 and len(drawing_dict['items']) > 2:
            width = drawing_dict['rect'][2] - drawing_dict['rect'][0]
            height = drawing_dict['rect'][3] - drawing_dict['rect'][1]
            if abs(width/height - 1) < 0.1 and width < 12:
                return True

        return False

    def _merge_overlapping_rects(self, drawings: List[DrawingElement]) -> List[DrawingElement]:
        """Iterates over drawings and merges any that have complete, or close to complete,
        overlaps

        Args:
            drawings (List[DrawingElement]): Drawings to potentially merge

        Returns:
            List[DrawingElement]: Drawings with any merged elements removed
        """

        did_merge = True
        while did_merge:
            did_merge = False
            merged_boxes = []
            merged = [False for _ in drawings]
            if len(drawings) > 1:
                for i, rect1 in enumerate(drawings[:-1]):
                    if merged[i]:
                        continue

                    for j, rect2 in enumerate(drawings[i+1:]):
                        if merged[j+i+1]:
                            continue
                        o1 = rect1.bbox.overlap(rect2.bbox, 'first')
                        o2 = rect1.bbox.overlap(rect2.bbox, 'second')
                        if o1 > 0.97 or o2 > 0.97:
                            if o1 > o2:
                                merged_boxes.append(rect2)
                            else:
                                merged_boxes.append(rect1)
                            merged[i] = True
                            merged[j+i+1] = True
                            self.logger.debug(
                                "Merged boxes %d and %d", i, j+i+1)
                            did_merge = True

                    if not merged[i]:
                        merged_boxes.append(rect1)

            if len(merged) > 0 and not merged[-1]:
                merged_boxes.append(drawings[-1])

            drawings = merged_boxes

        return merged_boxes


    def get_page_drawings(self, page: fitz.Page, page_colour: np.ndarray) -> Dict[DrawingType, List[DrawingElement]]:
        """Extract all drawings from the page and apply basic classification

        Args:
            page (fitz.Page): THe page to extract drawings from
            page_color (np.ndarray): The primary background colour of the page

        Returns:
            Dict[DrawingType, List[DrawingElement]]: Drawings found, separated by type
        """
        self.logger.debug("Starting drawing extraction")
        self.page = page
        bound = page.bound()
        self.page_bbox = Bbox(*bound, bound[2], bound[3])  # type:ignore
        
        processed_drawings: Dict[DrawingType, List[DrawingElement]] = {
            t: [] for t in DrawingType}
        for d in self.page.get_cdrawings():

            # Detect things that look like bullets
            if self._is_bullet(d):
                drawing = DrawingElement.from_dict(d, bound[2], bound[3], DrawingType.BULLET)
                processed_drawings[drawing.drawing_type].append(drawing)
                self.logger.debug(
                    "Found bullet with box %s", str(drawing.bbox))
                continue           

            is_meaningful_fill = 'f' in d['type'] and self._is_filled_rect(
                d, page_colour)
            is_meaningful_stroke = 's' in d['type'] and self._is_stroked_rect(
                d, page_colour)
            is_meaningful_rect = is_meaningful_fill or is_meaningful_stroke

            if is_meaningful_rect:
                drawing = DrawingElement.from_dict(d, bound[2], bound[3])
                drawing.bbox.x0 = max(drawing.bbox.x0, 0)
                drawing.bbox.y0 = max(drawing.bbox.y0, 0)
                drawing.bbox.x1 = min(drawing.bbox.x1, bound.x1)
                drawing.bbox.y1 = min(drawing.bbox.y1, bound.y1)

                if drawing.bbox.height() == 0:
                    drawing.bbox.y1 += 1.
                if drawing.bbox.width() == 0:
                    drawing.bbox.x1 += 1.

                overlap = drawing.bbox.overlap(self.page_bbox, normalisation='second')

                height = drawing.bbox.height()
                width = drawing.bbox.width()
                                
                if (height < 10 and width > min(30, height*3)) or (width < 10 and height > min(width*6, 30)):
                    if drawing.bbox.x_overlap(self.page_bbox) > 0 and drawing.bbox.y_overlap(self.page_bbox) > 0:
                        self.logger.debug("Found line %d with box %s",
                                          len(processed_drawings[DrawingType.LINE]), str(drawing.bbox))
                        drawing.drawing_type = DrawingType.LINE
                        processed_drawings[drawing.drawing_type].append(
                            drawing)
                        continue

                if overlap > 0.0005 and overlap < 0.55:
                    self.logger.debug("Found rectangle %d with box %s",
                                      len(processed_drawings[DrawingType.RECT]), str(drawing.bbox))
                    drawing.drawing_type = DrawingType.RECT
                    processed_drawings[drawing.drawing_type].append(drawing)

        # Merge boxes with significant overlap
        if self.merge_rects:
            processed_drawings[DrawingType.RECT] = \
                self._merge_overlapping_rects(processed_drawings[DrawingType.RECT])

        for t in processed_drawings:
            self.logger.debug("Found %d %s drawings", len(
                processed_drawings[t]), t.name)

        return processed_drawings
