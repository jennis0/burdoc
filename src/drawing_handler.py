from typing import List, Any
import logging
import fitz

from .layout_objects import Drawing
from .bbox import Bbox


class DrawingHandler(object):

    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.logger = logger.getChild('drawinghandler')
        self.page_bbox = None
        self.page = None
        self.page_bbox = None
        self.pdf = pdf
        self.merge_rects = True

    def _get_line_page_overlap(self, bbox: Any) -> float:
        x = bbox[2] - self.page_bbox[0] > 0 and bbox[2] > self.page_bbox[0]
        y = bbox[3] - self.page_bbox[1] > 0 and bbox[3] > self.page_bbox[1]
        return x and y

    def get_page_drawings(self, page: fitz.Page, merge_boxes=True) -> List[Drawing]:
        self.logger.debug("Starting drawing extraction")
        self.page = page
        self.page_bbox = Bbox(*page.bound())
        _,_,self.width,self.height = page.bound()

        processed_drawings = {t.name:[] for t in Drawing.DrawingType}
        for d in self.page.get_cdrawings():
            if d['type'] == 'f':
                if d['fill_opacity'] < 0.1:
                    continue

                drawing = Drawing(None, Bbox(*d['rect']), d['fill_opacity'])
                overlap = drawing.bbox.overlap(self.page_bbox, normalisation='second')

                if (drawing.bbox.height() < 10) or (drawing.bbox.width() < 10):
                    if overlap > 0:
                        self.logger.debug(f"Found line {len(processed_drawings['Line'])} with box {drawing.bbox}")
                        drawing.type = Drawing.DrawingType.Line
                        processed_drawings['Line'].append(drawing)
                        continue
                
                if overlap > 0.05 and overlap < 0.55:
                    self.logger.debug(f"Found rectangle {len(processed_drawings['Rect'])} with box {drawing.bbox}")
                    drawing.type = Drawing.DrawingType.Rect
                    processed_drawings['Rect'].append(drawing)

        #Merge boxes with significant overlap
        if self.merge_rects:
            did_merge = True
            to_process = processed_drawings['Rect']
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
                                self.logger.debug(f"Merged boxes {i} and {j+i+1}")
                                did_merge = True
                        
                        if not merged[i]:
                            merged_boxes.append(b1)

                if len(merged) > 0 and not merged[-1]:
                    merged_boxes.append(to_process[-1])

                to_process = merged_boxes

            processed_drawings['Rect'] = merged_boxes

        for t in processed_drawings:
            self.logger.debug(f"Found {len(processed_drawings[t])} {t} drawings")
        return processed_drawings