import logging
from typing import List, Optional
from fitz import Page
import numpy as np
import plotly.express as plt

from .layout_objects import LBlock, LTable
from .layout_graph import LayoutGraph
from .bbox import Bbox


class TableGenerator(object):

    def __init__(self, logger: logging.Logger):
        self.logger = logger.getChild('tablegen')


    def _generate_table_candidates(self, page: Page, blocks: List[LBlock]) -> List[List[LBlock]]:
        
        lg = LayoutGraph(self.logger, page.bound(), blocks)

        used_nodes = {b.id:False for b in lg.nodes}

        tables = []

        for b in lg.nodes[1:]:
            # if used_nodes[b.id]:
            #     continue

            if len(b.element.lines) == 0 or len(b.element.lines[0].spans) == 0:
                continue

            columns = [[b]]
            candidate = b

            self.logger.debug(f"Starting table search with seed {b.element}")

            if len(candidate.right) == 0:
                self.logger.debug(f"Skipping as seed due to no rightward text")
                continue

            col_edge = min([1000] + [lg.get_node(c).element.bbox.x0 for c in candidate.right])

            if abs(lg.get_node(candidate.right[0]).element.bbox.y0 - candidate.element.bbox.y0) > 20:
                self.logger.debug(f"Skipping as seed as no aligned right text")
                continue

            #Build first row by pushing as far down as possible in a straight line
            last_size = candidate.element.lines[0].spans[0].font.size
            last_length = sum([len(l.get_text()) for l in candidate.element.lines])
            while(True):
                
                #If there are no children we are at the end of the table
                if len(candidate.down) < 1:
                    self.logger.debug("Stopping as no more cells to check")
                    break

                #If the column splits in two we are at the end of the table
                elif len(candidate.down) > 1:
                    if abs(lg.get_node(candidate.down[0]).element.bbox.y0 - lg.get_node(candidate.down[1]).element.bbox.y0) < 0.5:
                        self.logger.debug("Stopping as column splits in two")
                        break
                
                candidate = lg.get_node(candidate.down[0])
                self.logger.debug(f"Considering {candidate.element} for first column")
                
                if len(candidate.element.lines) == 0:
                    self.logger.debug("Stopping as block is empty")
                    break

                if len(candidate.element.lines[0].spans) != 0:
                    size = candidate.element.lines[0].spans[0].font.size
                    if size > last_size+0.5:
                        self.logger.debug("Stopping as text size changed")
                        break

                    length = sum([len(l.get_text()) for l in candidate.element.lines])
                    if length > max(50, 4*last_length):
                        self.logger.debug("Stopping as next cell is too long")
                        break
                    last_length = max(length, last_length)


                if candidate.element.bbox.x1 > col_edge:
                    self.logger.debug(f"Skipping as it hits column edge")
                    break

                columns[0].append(candidate)

            self.logger.debug(f"{str(b.element)} - {len(columns[0])} candidate row blocks")

            #Build header row by pushing as far across as possible
            col_top = b.element.bbox.y0
            col_bottom = columns[0][-1].element.bbox.y1
            fontsize = b.element.lines[0].spans[0].font.size
            candidate = lg.get_node(columns[0][0].right[0])
            while (True):
                self.logger.debug(f"Considering {candidate.element} for header row")

                if len(candidate.element.lines) == 0 or len(candidate.element.lines[0].spans) == 0:
                    self.logger.debug(f"Skipping as empty")
                    break
                if abs(candidate.element.lines[0].spans[0].font.size - fontsize) > 0.0:
                    self.logger.debug(f"Skipping due to font mismatch")
                    break
                if abs(candidate.element.bbox.y0 - col_top) > 20:
                    self.logger.debug(f"Skipping as column would be too large")
                    break

                columns.append([candidate])

                if len(candidate.right) > 0:
                    if lg.get_node(candidate.right[-1]).element.bbox.y1 - col_bottom > 20:
                        break

                    candidate = lg.get_node(candidate.right[0])
                else:
                    break

            self.logger.debug(f"{str(b.element)} - {len(columns)} candidate columns")

            if len(columns) < 2:
                continue

            column_bboxes = [Bbox.merge([n.element.bbox for n in columns[0]])]

            for i,col in enumerate(columns[1:]):
                n = col[0]
                prev_boundary = column_bboxes[i].x1
                next_boundary = columns[i+2][0].element.bbox.x0 if len(columns) >= i+3 else 100000
                if len(n.down) > 0:
                    candidate = lg.get_node(n.down[0])

                    while(True):
                        self.logger.debug(f"Considering {candidate.element} for column {i+1}")
                        if candidate.element.bbox.x0 < prev_boundary or candidate.element.bbox.x1 > next_boundary:
                            self.logger.debug("Failed as crosses column boundary")
                            break
                        
                        if candidate.element.bbox.y0 - columns[0][-1].element.bbox.y1 > 30:
                            self.logger.debug("Failed as crosses bottom of table")
                            break

                        if candidate.element.bbox.y1 <= col_bottom + 200:
                            self.logger.debug("Added")
                            col.append(candidate)
                            if len(candidate.down) >= 1:
                                candidate = lg.get_node(candidate.down[0])
                                continue
                        else:
                            self.logger.debug("Failed as too large a gap from last cell")
                        
                        break
                
                self.logger.debug(f"Added {len(col) - 1} blocks to column {i+1}")
                column_bboxes.append(Bbox.merge([n.element.bbox for n in col]))

            # print("=======================================================")
            # for col in columns:
            #     for n in col:
            #         print(n.element, n.element.bbox)
            #     print("---------------------------------------------------")
            # print("=======================================================")
            # print()

            for i,c in enumerate(column_bboxes[1:]):
                self.logger.debug(f"{column_bboxes[0].y1} {c.y1}")
                if column_bboxes[0].y1 - c.y1 > 20:
                    columns = columns[:i+1]
            
            self.logger.debug(f"Filtered to {len(columns)} columns")        
     
            if len(columns) < 2:
                continue

            # print("=======================================================")
            # for col in columns:
            #     for n in col:
            #         print(n.element, n.element.bbox)
            #     print("---------------------------------------------------")
            # print("=======================================================")
            # print()

            for c in columns:
                for i,n in enumerate(c):
                    used_nodes[n.id] = True
                    c[i] = n.element

            tables.append(columns)

        return tables

    def _create_table_from_candidate(self, page: Page, candidate: List[List[LBlock]]) -> Optional[LTable]:
        #Generate bounding box for table
        self.logger.debug(f"Attempting to create table from seed {candidate[0][0]}")
        dims = candidate[0][0].bbox
        for col in candidate:
            for n in col:
                dims = Bbox.merge([dims, n.bbox])
        self.logger.debug(f"Scanning for table lines within {dims}")

        #Build array from individual lines so we can look for gaps
        arr = np.zeros(shape=(int(dims.y1 - dims.y0), int(dims.x1 - dims.x0)))
        for col in candidate:
            for b in col:
                for n in b.lines:
                    arr[
                        int(n.bbox.y0 - dims.y0):int(n.bbox.y1 - dims.y0),
                        int(n.bbox.x0 - dims.x0):int(n.bbox.x1 - dims.x0),
                        
                    ] = 1

        #Do the same for the first column to enable later comparisons - note we use
        #block granularity not line granularity to minimise possible number
        c1_arr = np.zeros(shape=(int(dims.y1 - dims.y0), int(dims.x1 - dims.x0)))
        for b in candidate[0]:
            c1_arr[
                int(b.bbox.y0 - dims.y0):int(b.bbox.y1 - dims.y0),
                int(b.bbox.x0 - dims.x0):int(b.bbox.x1 - dims.x0),
                
            ] = 1
      
        #Calculate all of the possible horizontal lines
        horizontal_array = np.zeros(arr.shape)
        horizontal_array = arr.sum(axis=1) == 0

        h_lines = []
        current_run = -1
        current_run_length = 0
        for i,v in enumerate(horizontal_array):
            if v > 0.5:
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

        #Calculate all of the possible horizontal lines for the first column
        c1_horizontal_array = np.zeros(c1_arr.shape)
        c1_horizontal_array = c1_arr.sum(axis=1) == 0

        c1_h_lines = []
        current_run = -1
        current_run_length = 0
        for i,v in enumerate(c1_horizontal_array):
            if v > 0.5:
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

        #Typically expect consistent numbers, especially given the first col is using blocks
        #Only expect to see more in first col when it is plain text and we're picking up 
        #block breaks
        if len(c1_h_lines) >= 1.5*len(h_lines):
            return None


        #Filter line breaks out of low density tables
        self.logger.debug(f"Found line candidates - {h_lines}")
        line_width = np.max([h[1] for h in h_lines])
        if line_width > 4:
            self.logger.debug("Filtering lines from low density table")
            h_lines = [h[0] + h[1]/2 + dims.y0 for h in h_lines if h[1] >= 3] + [100000]
        else:
            h_lines = [h[0] + h[1]/2 + dims.y0 for h in h_lines] + [100000]

        self.logger.debug(f"Found horizontal lines at {h_lines}")

        if len(h_lines) < 2:
            self.logger.debug(f"Table creation failed as no horizontal lines found.")
            return None

        #Not a table if a single cell takes up a huge quantity of a page.        
        h_dists = []
        for i in range(1, len(h_lines)-1):
            h_dists.append(h_lines[i] - h_lines[i-1])
        if any(h > 300 for h in h_dists):
            self.logger.debug(f"Table creation failed as row too large")
            return None

        # vertical_array = np.zeros(arr.shape)
        # vertical_array = arr.sum(axis=0) == 0
        #ah = np.repeat(horizontal_array[:,np.newaxis], arr.shape[1], axis=1)
        #av = np.repeat(vertical_array[np.newaxis,:], arr.shape[0], axis=0)
        #fig = plt.imshow(5*(ah + av) + arr)
        #fig.show()

        #Position lines within cells
        cells = []
        for i,col in enumerate(candidate):
            current_h_line = 0
            cells.append([])
            current_cell = []
            for bn in col:
                for line in bn.lines:
                    while line.bbox.y0 >= h_lines[current_h_line]:
                        if i == 0 and len(current_cell) == 0:
                            return None
                        cells[-1].append(current_cell)
                        current_cell = []
                        current_h_line += 1
                    current_cell.append(line)
            cells[-1].append(current_cell)

        #Throw away tables with mismatched columns - usually means not a real table!
        lengths = [len(col) for col in cells]
        max_len = max(lengths)
        if any((l - max_len) != 0 for l in lengths):
            self.logger.debug("Table creation failed due to inconsistent column length")
            return None

        #Throw away tables with identical columns and rows - usually means paragraphs
        if len(candidate) == 2:
            bound = page.bound()
            page_width = bound[2]
            w1 = max([e.bbox.width()/page_width for e in candidate[0]])
            w2 = max([e.bbox.width()/page_width for e in candidate[1]])
            h_widths = [h_lines[i]-h_lines[i-1] for i in range(1, len(h_lines)-1)]
            if len(h_widths) == 0:
                return 0
            h_var = max(h_widths) - min(h_widths)
            if h_var < 2 and w1 > 0.35 and w2 > 0.35 and abs(w1 - w2)/w1 < 0.05:
                self.logger.debug("Table creation failed as it's probably text")
                return None


        sizes = []
        for cell in cells[0][1:]:
            for line in cell:
                if len(line.spans) > 0:
                    sizes.append(line.spans[0].font.size)
        if len(set(sizes)) != 1:
            self.logger.debug("Table creation failed due header text in first column")
            return None

        #Check that the very first row is aligned
        print(cells[0][0])
        match_y = cells[0][0][0].bbox.y0 == cells[0][1][0].bbox.y0
        match_center = cells[0][0][0].bbox.center().y == cells[1][0][0].bbox.center().y
        if not (match_y or match_center):
            print( cells[0][0][0].bbox, cells[0][1][0].bbox)
            self.logger.debug("Table creation failed as top row not aligned")
            return None

        # print("=================================================================")
        # for i,c in enumerate(cells):
        #     for v in c:
        #         for block in v:
        #             aligns[i].append([block.bbox.y0, block.bbox.center().y])
        #             print(block)
        #         print()
        #     print("=------------------------------------------------------------=")
        # print("=================================================================")


        if cells[0][0][0].spans[0].font.bold:
            headers = [c[0] for c in cells]
            cells = [c[1:] for c in cells]

            rotated_cells = [[] for _ in range(len(cells[0]))]
            for c in cells:
                for i in range(len(c)):
                    rotated_cells[i].append(c[i])

            self.logger.debug(f"Found table with headers {headers}")
            return LTable(dims, headers, rotated_cells)

        rotated_cells = [[] for i in range(len(cells[0]))]
        for c in cells:
            for i in range(len(c)):
                rotated_cells[i].append(c[i])
        
        self.logger.debug(f"Found table with no headers")
        return LTable(dims, None, rotated_cells)


    def find_tables(self, page: Page, blocks: List[LBlock]) -> List[LTable]:
        candidates = self._generate_table_candidates(page, blocks)
        candidates.sort(key=lambda c: c[0][0].bbox.y0*10 + c[0][0].bbox.x0)

        tables = []
        for cand in candidates:
            skip = False
            for tab in tables:
                if cand[0][0].bbox.overlap(tab.bbox):
                    skip=True
                    break
            if not skip:
                tab = self._create_table_from_candidate(page, cand)
                if tab:
                    tables.append(tab)
        return tables
