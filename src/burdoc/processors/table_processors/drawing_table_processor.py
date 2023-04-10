import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from plotly.graph_objects import Figure

from ...elements import (Bbox, DrawingElement, DrawingType, Table, TableParts,
                         TextBlock)
from ...utils.render_pages import add_rect_to_figure
from ..processor import Processor


class DrawingTableProcessor(Processor):

    name: str = "drawing-table"

    def __init__(self, log_level: int = logging.INFO, max_threads: Optional[int] = None):
        super().__init__(DrawingTableProcessor.name, log_level, max_threads)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return [['drawing_elements', 'text_elements'], []]

    def generates(self) -> List[str]:
        return ["drawing_elements", 'text_elements', 'tables']

    def _merge_boxes(self, rects: List[DrawingElement]) -> List[DrawingElement]:
        if len(rects) == 0:
            return []

        table_boxes: List[DrawingElement] = []
        rects.sort(key=lambda x: x.bbox.y0*1000 + x.bbox.x0)
        merge_candidates = [[rects[0]]]

        for r in rects:
            last_bbox = merge_candidates[0][0].bbox

            if abs(r.bbox.y0 - last_bbox.y0) > 1 or \
                r.stroke_colour != merge_candidates[0][0].stroke_colour or \
                    r.fill_colour != merge_candidates[0][0].fill_colour:
                for mc in merge_candidates:
                    table_boxes.append(
                        DrawingElement(Bbox.merge([m.bbox for m in mc]), DrawingType.RECT)
                    )
                merge_candidates = [[r]]
                continue

            used = False
            for mc in merge_candidates:
                if abs(r.bbox.y1 - mc[0].bbox.y1) < 1 and \
                        abs(r.bbox.x0 - mc[-1].bbox.x1) < 3:
                    mc.append(r)
                    used = True
                    break
            if not used:
                merge_candidates.append([r])
                
        if len(merge_candidates) > 0:
            for mc in merge_candidates:
                table_boxes.append(
                        DrawingElement(Bbox.merge([m.bbox for m in mc]), DrawingType.RECT)
                    )
            
        table_boxes.sort(key=lambda x: x.bbox.y0*1000 + x.bbox.x0)
        merge_candidates = [[table_boxes[0]]]
        mc_open = [True]
        for r in table_boxes[1:]:

            used = False
            for i, mc in enumerate(merge_candidates):
                if not mc_open[i]:
                    continue
                if mc[-1].bbox.x_overlap(r.bbox) > 0.01:
                    if abs(r.bbox.x1 - mc[0].bbox.x1) < 1 and \
                            abs(r.bbox.x0 - mc[-1].bbox.x0) < 1 and \
                                abs(r.bbox.y0 - mc[-1].bbox.y1) < 100:
                        mc.append(r)
                        used = True
                else:
                    mc_open[i] = False

            if not used:
                merge_candidates.append([r])
                mc_open.append(True)


        full_table_boxes: List[DrawingElement] = []
        for mc in merge_candidates:
            if len(mc) > 1:
                full_table_boxes.append(DrawingElement(Bbox.merge([m.bbox for m in mc]), DrawingType.RECT))

        return full_table_boxes

    def _rects_to_arrays(self, rects: List[DrawingElement]) -> List[np.ndarray]:
        lines = []

        rects = self._merge_boxes(rects)

        for b in rects:
            lines += [
                DrawingElement(Bbox(b.bbox.x0, b.bbox.y0, b.bbox.x0, b.bbox.y1,
                                    b.bbox.page_width, b.bbox.page_height), DrawingType.LINE),
                DrawingElement(Bbox(b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y0,
                                    b.bbox.page_width, b.bbox.page_height), DrawingType.LINE),
                DrawingElement(Bbox(b.bbox.x1, b.bbox.y0, b.bbox.x1, b.bbox.y1,
                                    b.bbox.page_width, b.bbox.page_height), DrawingType.LINE),
                DrawingElement(Bbox(b.bbox.x0, b.bbox.y1, b.bbox.x1, b.bbox.y1,
                                    b.bbox.page_width, b.bbox.page_height), DrawingType.LINE),
            ]

        arrays = self._merge_lines(lines, True)
        arrays += self._merge_lines(lines, False)

        return arrays

    def _merge_lines(self, lines: List[DrawingElement], vertical: bool) -> List[np.ndarray]:
        if len(lines) == 0:
            return []

        if vertical:
            lines.sort(key=lambda l: l.bbox.x0*1000 + l.bbox.y0)
        else:
            lines.sort(key=lambda l: l.bbox.y0*1000 + l.bbox.x0)

        arrays: List[np.ndarray] = []
        merged_line_candidates = [[lines[0]]]
        for l in lines[1:]:
            last_bbox = merged_line_candidates[0][0].bbox

            # Only consider thin lines
            if vertical:
                if abs(l.bbox.x0 - l.bbox.x1) > 3:
                    continue
            else:
                if abs(l.bbox.y0 - l.bbox.y1) > 3:
                    continue

            # If on new line, merge current candidate
            if vertical:
                offset = abs(l.bbox.x0 - last_bbox.x0)
            else:
                offset = abs(l.bbox.y0 - last_bbox.y0)

            if offset > 1:
                for mlc in merged_line_candidates:
                    merged_bbox = Bbox.merge([m.bbox for m in mlc])
                    arrays.append(np.array([merged_bbox.x0, merged_bbox.y0, merged_bbox.x1, merged_bbox.y1]))
                merged_line_candidates = [[l]]
                continue

            used = False
            for mlc in merged_line_candidates:
                if vertical:
                    end_distance = abs(mlc[-1].bbox.y1 - l.bbox.y0)
                else:
                    end_distance = abs(mlc[-1].bbox.x1 - l.bbox.x0)

                if end_distance < 1:
                    used = True
                    mlc.append(l)
                    break

            if not used:
                merged_line_candidates.append([l])

        if len(merged_line_candidates) > 0:
            for mlc in merged_line_candidates:
                merged_bbox = Bbox.merge([m.bbox for m in mlc])
                arrays.append(np.array([merged_bbox.x0, merged_bbox.y0, merged_bbox.x1, merged_bbox.y1]))

        return arrays

    def _lines_rects_to_arrays(self, elements: Dict[DrawingType, List[DrawingElement]]) -> List[np.ndarray]:

        lines = elements[DrawingType.LINE]
        arrays: List[np.ndarray] = []

        arrays = self._merge_lines(lines, True)
        arrays += self._merge_lines(lines, False)

        arrays += self._rects_to_arrays(elements[DrawingType.RECT])

        return arrays

    def _process(self, data: Any) -> Any:

        if 'tables' not in data:
            data['tables'] = {}

        for page_number, drawings, text in self.get_page_data(data):
            print(page_number)
            rects = self._lines_rects_to_arrays(drawings)
            # for r in rects:
            #     print(r)
            #drawings[DrawingType.LINE] = []  # [DrawingElement(

            # Bbox(r[0], r[1], r[2], r[3], 1000, 1000), 1.0, DrawingType.LINE) for r in rects]
            #drawings[DrawingType.RECT] = self._merge_boxes(drawings[DrawingType.RECT])

            data['tables'][page_number] = []

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):

        colours = {
            DrawingType.LINE: "Green",
            DrawingType.RECT: "Blue",
        }

        for dr_type in data['drawing_elements'][page_number]:
            if dr_type in colours:
                colour = colours[dr_type]
                for dr in data['drawing_elements'][page_number][dr_type]:
                    add_rect_to_figure(fig, dr.bbox, colour)
                fig.add_scatter(x=[None], y=[None], name=f"{dr_type.name}", line=dict(
                    width=3, color=colour))
