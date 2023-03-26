import logging
from typing import Dict, List

import fitz

from ...elements import Bbox, DrawingElement, DrawingType
from ...utils.logging import get_logger


class DrawingHandler(object):
    """Extracts drawings from a PDF and applies standardisation and basic type inference
    """

    def __init__(self, pdf: fitz.Document, log_level: int=logging.INFO):
        self.logger = get_logger('drawing-handler', log_level=log_level)
        self.page_bbox: Bbox = None #type:ignore
        self.page: fitz.Page = None #type:ignore
        self.pdf: fitz.Document = pdf
        self.merge_rects = True

    def get_page_drawings(self, page: fitz.Page) -> Dict[DrawingType, List[DrawingElement]]:
        """Extract all drawings from the page and apply basic classification

        Args:
            page (fitz.Page)

        Returns:
            Dict[DrawingType, List[DrawingElement]]: Drawings found, separated by type
        """
        self.logger.debug("Starting drawing extraction")
        self.page = page
        bound = page.bound()
        self.page_bbox = Bbox(*bound, bound[2], bound[3]) #type:ignore

        processed_drawings: Dict[DrawingType, List[DrawingElement]] = {t:[] for t in DrawingType}
        for d in self.page.get_cdrawings():
            if d['type'] == 'f' and d['fill_opacity'] > 0.9 and len(d['items']) > 2:
                width = d['rect'][2] - d['rect'][0]
                height = d['rect'][3] - d['rect'][1]
                if abs(width/height - 1) < 0.1 and width < 5:
                    drawing =  DrawingElement(bbox = Bbox(*d['rect'], bound[2], bound[3]), #type:ignore
                                    drawing_type=DrawingType.BULLET, opacity=d['fill_opacity']
                                )
                    processed_drawings[drawing.drawing_type].append(drawing)
                    self.logger.debug("Found bullet with box %s", str(drawing.bbox))
                    continue
                
            if d['type'] == 'f':
                if d['fill_opacity'] < 0.1:
                    self.logger.debug("Filtered drawing due to low fill opacity")
                    continue

                drawing = DrawingElement(bbox=Bbox(*d['rect'], bound[2], bound[3]), #type:ignore
                                         drawing_type=DrawingType.UNKNOWN, 
                                         opacity=d['fill_opacity'])
                drawing.bbox.x0 = max(drawing.bbox.x0, 0)
                drawing.bbox.y0 = max(drawing.bbox.y0, 0)
                drawing.bbox.x1 = min(drawing.bbox.x1, bound.x1)
                drawing.bbox.y1 = min(drawing.bbox.y1, bound.y1)
                overlap = drawing.bbox.overlap(self.page_bbox, normalisation='second')

                if (drawing.bbox.height() < 10) or (drawing.bbox.width() < 10):
                    if overlap > 0:
                        self.logger.debug("Found line %d with box %s", 
                                          len(processed_drawings[DrawingType.LINE]), str(drawing.bbox))
                        drawing.drawing_type = DrawingType.LINE
                        processed_drawings[drawing.drawing_type].append(drawing)
                        continue
                
                if overlap > 0.001 and overlap < 0.55:
                    self.logger.debug("Found rectangle %d with box %s",
                                      len(processed_drawings[DrawingType.RECT]), str(drawing.bbox))
                    drawing.drawing_type = DrawingType.RECT
                    processed_drawings[drawing.drawing_type].append(drawing)

        #Merge boxes with significant overlap
        if self.merge_rects and DrawingType.RECT:
            did_merge = True
            to_process = processed_drawings[DrawingType.RECT]
            while did_merge:
                did_merge = False
                merged_boxes = []
                merged = [False for b in to_process]
                if len(to_process) > 1:
                    for i,b1 in enumerate(to_process[:-1]):
                        if merged[i]:
                            continue

                        for j,b2 in enumerate(to_process[i+1:]):
                            if merged[j+i+1]:
                                continue
                            o1 = b1.bbox.overlap(b2.bbox, 'first')
                            o2 = b1.bbox.overlap(b2.bbox, 'second') 
                            if o1 > 0.97 or o2 > 0.97:
                                if o1 > o2:
                                    merged_boxes.append(b2)
                                else:
                                    merged_boxes.append(b1)
                                merged[i] = True
                                merged[j+i+1] = True
                                self.logger.debug("Merged boxes %d and %d", i, j+i+1)
                                did_merge = True
                        
                        if not merged[i]:
                            merged_boxes.append(b1)

                if len(merged) > 0 and not merged[-1]:
                    merged_boxes.append(to_process[-1])

                to_process = merged_boxes

            processed_drawings[DrawingType.RECT] = merged_boxes

        for t in processed_drawings:
            self.logger.debug("Found %d %s drawings", len(processed_drawings[t]), t.name )

        return processed_drawings