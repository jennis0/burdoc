import logging
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np

from ...elements import Bbox, PageSection, TablePart, TextBlock
from ...utils.layout_graph import LayoutGraph
from .table_extractor_strategy import TableExtractorStrategy


class RulesTableStrategy(TableExtractorStrategy):
    """Applies a simple rules-based algorithm to identify tables in text.
    This looks for patterns in text blocks and makes no use of lines/images.
    Very good at pulling out dense inline tables missed by the ML algorithms.

    Requires: ['page_bounds', 'elements']
    Optional: []
    Generates: ['tables', 'elements']
    """

    def __init__(self, log_level: int = logging.INFO):
        super().__init__('rules', log_level=log_level)

    @staticmethod
    def requirements() -> List[str]:
        return ['page_bounds', 'elements']
    
    @staticmethod
    def generates() -> List[str]:
        return []
    
    def extract_tables(self, page_numbers: List[int], fields: Dict[str, Dict[int, Any]]
                       ) -> Dict[int, List[List[Tuple[TablePart, Bbox]]]]:

        page_bounds: Dict[int, Bbox] = fields['page_bounds']
        elements: Dict[int, List[PageSection]] = fields['elements']

        results: Dict[int, List[List[Tuple[TablePart, Bbox]]]] = {p: [] for p in page_numbers}

        for page_number in page_numbers:
            page_bound = page_bounds[page_number]
            page_elements = elements[page_number]

            for section in page_elements:
                table_candidates = self._generate_table_candidates(
                    page_bound, [i for i in section.items if isinstance(i, TextBlock)])
                table_candidates.sort(
                    key=lambda c: c[0][0].bbox.y0*10 + c[0][0].bbox.x0)

                section_tables: List[List[Tuple[TablePart, Bbox]]] = []
                for cand in table_candidates:
                    skip = False
                    for tab in section_tables:
                        if cand[0][0].bbox.overlap(tab[0][1]):
                            skip = True
                            break
                    if not skip:
                        table_parts = self._create_table_from_candidate(cand)
                        if table_parts:
                            section_tables.append(table_parts)

                if len(section_tables) == 0:
                    continue

                results[page_number] += section_tables

        return results

    def _generate_table_candidates(self, page_bound: Bbox, blocks: List[TextBlock]) -> List[List[List[TextBlock]]]:

        layout_graph = LayoutGraph(page_bound, blocks)

        used_nodes = {node.node_id: False for node in layout_graph.nodes}

        tables: List[List[List[TextBlock]]] = []

        # If there are no pieces of text crossing the centre of the page, assume we
        # are dealing with a 2 column layout.
        if layout_graph.matrix.sum(axis=1)[int(layout_graph.matrix.shape[0] / 2)] == 0:
            boundary = layout_graph.matrix.shape[0] / 2
        else:
            boundary = layout_graph.matrix.shape[0] + 10

        for node in layout_graph.nodes[1:]:
            # if used_nodes[b.id]:
            #     continue

            if len(node.element.items) == 0 or len(node.element.items[0].spans) == 0:  # type:ignore

                continue

            columns = [[node]]
            candidate = node

            self.logger.debug(
                "Starting table search with seed %s", node.element)

            if len(candidate.right) == 0:
                self.logger.debug("Skipping as seed due to no rightward text")
                continue

            col_edge = min(
                [1000] + [layout_graph.get_node(c).element.bbox.x0 for c in candidate.right])
            top_edge = candidate.element.bbox.y0
            top_center = candidate.element.bbox.center().y

            if abs(layout_graph.get_node(candidate.right[0]).element.bbox.y0 - top_edge) > 5 \
                    and abs(layout_graph.get_node(candidate.right[0]).element.bbox.center().y - top_center) > 5:
                self.logger.debug("Skipping as seed as no aligned right text")
                continue

            # Build first column by pushing as far down as possible in a straight line
            candidate_element = cast(TextBlock, candidate.element)
            last_size = candidate_element.items[0].spans[0].font.size
            last_length = sum([len(l.get_text())
                              for l in candidate_element.items])
            while True:

                # If there are no children we are at the end of the table
                if len(candidate.down) < 1:
                    break

                # If the column splits in two we are at the end of the table
                if len(candidate.down) > 1:
                    if abs(layout_graph.get_node(candidate.down[0]).element.bbox.y0 -
                           layout_graph.get_node(candidate.down[1]).element.bbox.y0) < 0.5:
                        break

                candidate = layout_graph.get_node(candidate.down[0])
                candidate_element = cast(TextBlock, candidate.element)
                self.logger.debug(
                    "Considering %s for next column with text %s", str(candidate), candidate_element.get_text())

                # If its an empty element we're at end of table
                if len(candidate_element.items) == 0:
                    break

                # If there's an increase in font size we're at end of table or if amount of
                # text changes drastically
                if len(candidate_element.items[0].spans) != 0:
                    size = candidate_element.items[0].spans[0].font.size
                    if size > last_size+0.5:
                        self.logger.debug(
                            "Skipping due to text size increasing")
                        break

                    length = sum([len(l.get_text())
                                 for l in candidate_element.items])
                    if len(columns[0]) > 1 and length > 4*last_length and length > 20:
                        self.logger.debug(
                            "Skipping due to text length disparity")
                        break
                    last_length = max(length, last_length)

                # If col width would intersect with right edge we're at end of table
                if candidate.element.bbox.x1 > col_edge:
                    self.logger.debug("Skipping as it hits column edge")
                    break

                columns[0].append(candidate)

            self.logger.debug("%s - %s candidate row blocks",
                              str(node.element), len(columns[0]))

            # Build header row by pushing as far across as possible
            col_top = node.element.bbox.y0
            fontsize = cast(
                TextBlock, node.element).items[0].spans[0].font.size

            col_bottom = columns[0][-1].element.bbox.y1
            candidate = layout_graph.get_node(columns[0][0].right[0])
            candidate_element = cast(TextBlock, candidate.element)
            while True:
                self.logger.debug(
                    "Considering %s for header row", candidate_element)
                if columns[0][0].element.bbox.x0 < boundary and candidate_element.bbox.x1 > boundary:
                    self.logger.debug("Skipping as crosses x boundary")
                    break
                if len(candidate_element.items) == 0 or len(candidate_element.items[0].spans) == 0:
                    self.logger.debug("Skipping as empty")
                    break
                if abs(candidate_element.items[0].spans[0].font.size - fontsize) > 0.0:
                    self.logger.debug("Skipping due to font mismatch")
                    break
                if abs(candidate_element.bbox.y0 - col_top) > 20:
                    self.logger.debug("Skipping as column would be too large")
                    break

                columns.append([candidate])

                if len(candidate.right) > 0:
                    if layout_graph.get_node(candidate.right[-1]).element.bbox.y1 - col_bottom > 20:
                        break

                    candidate = layout_graph.get_node(candidate.right[0])
                else:
                    break

            self.logger.debug("%s - %s candidate columns",
                              str(node.element), len(columns[0]))

            if len(columns) < 2:
                continue

            column_bboxes = [Bbox.merge([n.element.bbox for n in columns[0]])]

            for i, col in enumerate(columns[1:]):
                node = col[0]
                prev_boundary = column_bboxes[i].x1
                next_boundary = columns[i +
                                        2][0].element.bbox.x0 if len(columns) >= i+3 else 100000
                if len(node.down) > 0:
                    candidate = layout_graph.get_node(node.down[0])

                    while True:
                        self.logger.debug(
                            "Considering %s for column %d", candidate.element, i+1)
                        if candidate.element.bbox.x0 < prev_boundary or candidate.element.bbox.x1 > next_boundary:
                            self.logger.debug(
                                "Failed as crosses column boundary")
                            break

                        if candidate.element.bbox.y0 - columns[0][-1].element.bbox.y1 > 30:
                            self.logger.debug(
                                "Failed as crosses bottom of table")
                            break

                        if candidate.element.bbox.y1 <= col_bottom + 200:
                            self.logger.debug("Added")
                            col.append(candidate)
                            if len(candidate.down) >= 1:
                                candidate = layout_graph.get_node(
                                    candidate.down[0])
                                continue
                        else:
                            self.logger.debug(
                                "Failed as too large a gap from last cell")

                        break

                self.logger.debug(
                    "Added %d blocks to column %d", len(col) - 1, i+1)
                column_bboxes.append(Bbox.merge([n.element.bbox for n in col]))

            for i, row in enumerate(column_bboxes[1:]):
                self.logger.debug("%f - %f", column_bboxes[0].y1, row.y1)
                if column_bboxes[0].y1 - row.y1 > 20:
                    columns = columns[:i+1]
                    break

            self.logger.debug("Filtered to %d columns", len(columns))

            if len(columns) < 2:
                continue

            columns_as_elements: List[List[TextBlock]] = [[] for c in columns]
            for i, col in enumerate(columns):
                for node in col:
                    used_nodes[node.node_id] = True
                    columns_as_elements[i].append(
                        cast(TextBlock, node.element))

            tables.append(columns_as_elements)

        return tables

    def _create_table_from_candidate(self, candidate: List[List[TextBlock]]) -> Optional[List[Tuple[TablePart, Bbox]]]:
        # Generate bounding box for table
        self.logger.debug(
            "Attempting to create table from seed %s", candidate[0][0])
        dims = candidate[0][0].bbox
        for column in candidate:
            for text_block in column:
                dims = Bbox.merge([dims, text_block.bbox])
        self.logger.debug("Scanning for table lines within %s", dims)

        # Build array from individual lines so we can look for gaps
        arr = np.zeros(shape=(int(dims.y1 - dims.y0), int(dims.x1 - dims.x0)))
        for column in candidate:
            for text_block in column:
                for line in text_block:
                    arr[
                        int(line.bbox.y0 - dims.y0):int(line.bbox.y1 - dims.y0),
                        int(line.bbox.x0 - dims.x0):int(line.bbox.x1 - dims.x0),

                    ] = 1

        # Do the same for the first column to enable later comparisons - note we use
        # block granularity not line granularity to minimise possible number
        c1_arr = np.zeros(
            shape=(int(dims.y1 - dims.y0), int(dims.x1 - dims.x0)))
        for text_block in candidate[0]:
            for line in text_block:
                c1_arr[
                    int(line.bbox.y0 - dims.y0):int(line.bbox.y1 - dims.y0),
                    int(line.bbox.x0 - dims.x0):int(line.bbox.x1 - dims.x0),

                ] = 1

        # Calculate all of the possible horizontal lines
        horizontal_array = np.zeros(arr.shape)
        horizontal_array = arr.sum(axis=1) == 0

        h_lines: List[Tuple[int, int]] = []
        current_run = -1
        current_run_length = 0
        for i, y in enumerate(horizontal_array):
            if y > 0.5:
                if current_run >= 0:
                    current_run_length += 1
                else:
                    current_run_length = 1
                    current_run = i
            else:
                if current_run >= 0:
                    h_lines.append((current_run, current_run_length))
                    current_run = -1

        if current_run >= 0:
            h_lines.append((current_run, current_run_length))

        # Calculate all of the possible horizontal lines for the first column
        c1_horizontal_array = np.zeros(c1_arr.shape)
        c1_horizontal_array = c1_arr.sum(axis=1) == 0

        c1_h_lines: List[Tuple[int, int]] = []
        current_run = -1
        current_run_length = 0
        for i, y in enumerate(c1_horizontal_array):
            if y > 0.5:
                if current_run >= 0:
                    current_run_length += 1
                else:
                    current_run_length = 1
                    current_run = i
            else:
                if current_run >= 0:
                    c1_h_lines.append((current_run, current_run_length))
                    current_run = -1

        if current_run >= 0:
            c1_h_lines.append((current_run, current_run_length))

        # Typically expect consistent numbers, especially given the first col is using blocks
        # Only expect to see more in first col when it is plain text and we're picking up
        # block breaks
        if len(c1_h_lines) >= 2*len(h_lines):
            return None

        # Filter line breaks out of low density tables
        self.logger.debug("Found line candidates - %s", str(h_lines))
        line_width = np.max([h[1] for h in h_lines])
        if line_width > 4:
            self.logger.debug("Filtering lines from low density table")
            h_line_centers = [dims.y0] + [h[0] + h[1]/2 +
                                          dims.y0 for h in h_lines if h[1] >= 3] + [dims.y1]
        else:
            h_line_centers = [dims.y0] + [h[0] + h[1] /
                                          2 + dims.y0 for h in h_lines] + [dims.y1]

        self.logger.debug("Found horizontal lines at %s", str(h_lines))

        if len(h_line_centers) < 2:
            self.logger.debug(
                "Table creation failed as no horizontal lines found.")
            return None

        # Not a table if a single cell takes up a huge quantity of a page.
        h_dists = []
        for i in range(1, len(h_line_centers)-1):
            h_dists.append(h_line_centers[i] - h_line_centers[i-1])
        if any(h > 300 for h in h_dists):
            self.logger.debug("Table creation failed as row too large")
            return None

        vertical_array = np.zeros(arr.shape)
        vertical_array = arr.sum(axis=0) == 0

        # Calculate all of the possible vertical lines
        v_lines: List[Tuple[int, int]] = []
        current_run = -1
        current_run_length = 0
        for i, y in enumerate(vertical_array):
            if y > 0.5:
                if current_run >= 0:
                    current_run_length += 1
                else:
                    current_run_length = 1
                    current_run = i
            else:
                if current_run >= 0:
                    v_lines.append((current_run, current_run_length))
                    current_run = -1

        if current_run >= 0:
            v_lines.append((current_run, current_run_length))

        v_line_centers = [dims.x0] + [v[0] + v[1] /
                                      2 + dims.x0 for v in v_lines] + [dims.x1]

        # ah = np.repeat(horizontal_array[:,np.newaxis], arr.shape[1], axis=1)
        # av = np.repeat(vertical_array[np.newaxis,:], arr.shape[0], axis=0)
        # fig = plt.imshow(5*(ah + av) + arr)
        # fig.show()

        parts = [(TablePart.TABLE, dims.clone())]
        for i in range(len(h_line_centers) - 1):
            parts.append(
                (TablePart.ROW, Bbox(
                    dims.x0, h_line_centers[i], dims.x1, h_line_centers[i+1], dims.page_width, dims.page_height))
            )

        for i in range(len(v_line_centers) - 1):
            parts.append(
                (TablePart.COLUMN, Bbox(
                    v_line_centers[i], dims.y0, v_line_centers[i+1], dims.y1, dims.page_width, dims.page_height))
            )

        return parts
