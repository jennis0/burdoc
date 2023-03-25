import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from plotly.graph_objects import Figure

from ..elements.bbox import Bbox
from ..elements.table import Table
from ..elements.textblock import TextBlock
from ..table_strategies.table_extractor_strategy import TableExtractorStrategy
from ..utils.layout_graph import LayoutGraph
from .processor import Processor


class RulesTableProcessor(Processor):
    """Applies a simple rules-based algorithm to identify tables in text.
    This looks for patterns in text blocks and makes no use of lines/images.
    Very good at pulling out dense inline tables missed by the ML algorithms.

    Requires: ['page_bounds', 'elements']
    Optional: []
    Generates: ['tables', 'elements']
    """
    
    name: str = 'rules-table'

    def __init__(self, log_level: int=logging.INFO):
        super().__init__(RulesTableProcessor.name, log_level=log_level)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (['page_bounds', 'elements'], [])
    
    def generates(self) -> List[str]:
        return ['tables', 'elements']
          
    def _process(self, data: Any) -> Any:
        if 'tables' not in data:
            data['tables'] = {}
        for pn, page_bound, page_elements in self.get_page_data(data):
            if pn not in data['tables']:
                data['tables'][pn] = []

            for section in page_elements:
                table_candidates = self._generate_table_candidates(page_bound, [i for i in section.items if isinstance(i, TextBlock)])
                table_candidates.sort(key=lambda c: c[0][0].bbox.y0*10 + c[0][0].bbox.x0)
                
                section_tables = []
                for cand in table_candidates:
                    skip = False
                    for tab in section_tables:
                        if cand[0][0].bbox.overlap(tab[0][1]):
                            skip=True
                            break
                    if not skip:
                        tab_parts = self._create_table_from_candidate(cand)
                        if tab_parts:
                            section_tables.append(tab_parts)

                if len(section_tables) == 0:
                    continue

                table_elements = []
                for table_bbox, structure in section_tables:
                    row_headers = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.ROWHEADER]
                    rows = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.ROW]
                    col_headers = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.COLUMNHEADER]
                    cols = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.COLUMN]
                
                    rs = col_headers + rows
                    cs = row_headers + cols

                    if len(cs) == 2:
                        if cs[0][1].width() / cs[1][1].width() > 0.9:
                            continue

                    merges  = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.SPANNINGCELL]

                    table_elements.append(Table(table_bbox[1], [[[] for _ in cs] for _ in rs], 
                                            row_boxes=rs, col_boxes=cs, merges=merges))
                

                bad_lines = np.array([0 for _ in table_elements])
                used_text = np.array([-1 for _ in section.items])
                for element_index,element in enumerate(section.items):
                    e_bbox = element.bbox

                    if not isinstance(element, TextBlock):
                        continue

                    for table_index,table in enumerate(table_elements):
                        table_element_x_overlap = e_bbox.x_overlap(table.bbox, 'first')
                        table_element_y_overlap = e_bbox.y_overlap(table.bbox, 'first')

                        if table_element_x_overlap > 0.9 and table_element_y_overlap > 0.9:
                            
                            for line in element.items:
                                candidate_row_index = -1
                                for row_index,row in enumerate(table.row_boxes):
                                    if line.bbox.y_overlap(row[1], 'first') > 0.8:
                                        candidate_row_index = row_index
                                        break
                                if candidate_row_index < 0:
                                    bad_lines[table_index] += 1
                                    continue

                                candidate_col_index = -1
                                for col_index,col in enumerate(table.col_boxes):
                                    if line.bbox.x_overlap(col[1], 'first') > 0.8:
                                        candidate_col_index = col_index
                                        break
                                if candidate_col_index < 0:
                                    bad_lines[table_index] += 1
                                    continue

                                table._cells[candidate_row_index][candidate_col_index].append(line)
                            
                            used_text[element_index] = table_index
                            break
                            
                        elif table_element_x_overlap * table_element_y_overlap > 0.02:
                            bad_lines[table_index] += 1


                for element_index,z in enumerate(zip(table_elements, bad_lines)):
                    table = z[0]
                    bl = z[1]
                    if bl > 0:
                        used_text[used_text == element_index] = -1
                        continue

                    skip = False
                    for row in table._cells:
                        if len(row[0]) == 0:
                            skip = True
                            break
                    if skip:
                        used_text[used_text == element_index] = -1
                        continue

                    data['tables'][pn].append(table)

                # Remove any items that have been pulled into the table
                section.items = [i for i,u in zip(section.items, used_text) if u < 0]


    def add_generated_items_to_fig(self, page_number:int, fig: Figure, data: Dict[str, Any]):
        colours = {
            "table":"Cyan",
            "cell":"LightGrey",
            'row': "Grey",
            "col": "LightGrey",
            "merges": "Turquoise"
        }

        def add_rect(fig, bbox, colour):
            fig.add_shape(
                type='rect', xref='x', yref='y', opacity=0.6,
                x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
                line=dict(color=colour, width=3)
            )

        for t in data['tables'][page_number]:
            add_rect(fig, t.bbox, colours["table"])

            row_bboxes = [r[1] for r in t.row_boxes]
            col_bboxes = [c[1] for c in t.col_boxes]
            for rb in t.row_boxes:
                add_rect(fig, rb[1], colours['row'])
            for cb in t.col_boxes:
                add_rect(fig, cb[1], colours['col'])
            for sb in t.merges:
                add_rect(fig, sb[1], colours['merges'])



        fig.add_scatter(x=[None], y=[None], name="Table", line=dict(width=3, color=colours["table"]))        

    def _generate_table_candidates(self, page_bound: Bbox, blocks: List[TextBlock]) -> List[List[TextBlock]]:
        
        lg = LayoutGraph(self.logger, page_bound, blocks)

        used_nodes = {b.id:False for b in lg.nodes}

        tables = []

        #If there are no pieces of text crossing the centre of the page, assume we
        #are dealing with a 2 column layout.
        if lg.matrix.sum(axis=1)[int(lg.matrix.shape[0] / 2)] == 0:
            boundary = lg.matrix.shape[0] / 2
        else:
            boundary = lg.matrix.shape[0] + 10

        for b in lg.nodes[1:]:
            # if used_nodes[b.id]:
            #     continue

            if len(b.element.items) == 0 or len(b.element.items[0].spans) == 0:
                continue

            columns = [[b]]
            candidate = b

            self.logger.debug(f"Starting table search with seed {b.element}")

            if len(candidate.right) == 0:
                self.logger.debug(f"Skipping as seed due to no rightward text")
                continue

            col_edge = min([1000] + [lg.get_node(c).element.bbox.x0 for c in candidate.right])
            top_edge = candidate.element.bbox.y0
            top_center = candidate.element.bbox.center().y

            if abs(lg.get_node(candidate.right[0]).element.bbox.y0 - top_edge) > 5 \
             and abs(lg.get_node(candidate.right[0]).element.bbox.center().y - top_center) > 5:
                self.logger.debug(f"Skipping as seed as no aligned right text")
                continue

            #Build first column by pushing as far down as possible in a straight line
            last_size = candidate.element.items[0].spans[0].font.size
            last_length = sum([len(l.get_text()) for l in candidate.element.items])
            while(True):
                
                #If there are no children we are at the end of the table
                if len(candidate.down) < 1:
                    break

                #If the column splits in two we are at the end of the table
                elif len(candidate.down) > 1:
                    if abs(lg.get_node(candidate.down[0]).element.bbox.y0 - lg.get_node(candidate.down[1]).element.bbox.y0) < 0.5:
                        break
                
                candidate = lg.get_node(candidate.down[0])
                self.logger.debug(f"Considering {candidate.element} for next column")
                
                #If its an empty element we're at end of table
                if len(candidate.element.items) == 0:
                    break

                #If there's an increase in font size we're at end of table or if amount of
                # text changes drastically
                if len(candidate.element.items[0].spans) != 0:
                    size = candidate.element.items[0].spans[0].font.size
                    if size > last_size+0.5:
                        self.logger.debug("Skipping due to text size increasing")
                        break

                    length = sum([len(l.get_text()) for l in candidate.element.items])
                    if length > 4*last_length and length > 20:
                        self.logger.debug("Skipping due to text length disparity")
                        break
                    last_length = max(length, last_length)

                #If col width would intersect with right edge we're at end of table
                if candidate.element.bbox.x1 > col_edge:
                    self.logger.debug(f"Skipping as it hits column edge")
                    break

                columns[0].append(candidate)

            self.logger.debug(f"{str(b.element)} - {len(columns[0])} candidate row blocks")

            #Build header row by pushing as far across as possible
            col_top = b.element.bbox.y0
            col_bottom = columns[0][-1].element.bbox.y1
            fontsize = b.element.items[0].spans[0].font.size
            candidate = lg.get_node(columns[0][0].right[0])
            while (True):
                self.logger.debug(f"Considering {candidate.element} for header row")
                if columns[0][0].element.bbox.x0 < boundary and candidate.element.bbox.x1 > boundary:
                    self.logger.debug("Skipping as crosses x boundary")
                    break
                if len(candidate.element.items) == 0 or len(candidate.element.items[0].spans) == 0:
                    self.logger.debug(f"Skipping as empty")
                    break
                if abs(candidate.element.items[0].spans[0].font.size - fontsize) > 0.0:
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

            for i,c in enumerate(column_bboxes[1:]):
                self.logger.debug(f"{column_bboxes[0].y1} {c.y1}")
                if column_bboxes[0].y1 - c.y1 > 20:
                    columns = columns[:i+1]
                    break

            self.logger.debug(f"Filtered to {len(columns)} columns")        
     
            if len(columns) < 2:
                continue

            for c in columns:
                for i,n in enumerate(c):
                    used_nodes[n.id] = True
                    c[i] = n.element

            tables.append(columns)

        return tables
    
    def _create_table_from_candidate(self, candidate: List[List[TextBlock]]) -> Optional[Table]:
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
            for block in col:
                for n in block.items:
                    arr[
                        int(n.bbox.y0 - dims.y0):int(n.bbox.y1 - dims.y0),
                        int(n.bbox.x0 - dims.x0):int(n.bbox.x1 - dims.x0),
                        
                    ] = 1

        #Do the same for the first column to enable later comparisons - note we use
        #block granularity not line granularity to minimise possible number
        c1_arr = np.zeros(shape=(int(dims.y1 - dims.y0), int(dims.x1 - dims.x0)))
        for block in candidate[0]:
            for line in block:
                c1_arr[
                    int(line.bbox.y0 - dims.y0):int(line.bbox.y1 - dims.y0),
                    int(line.bbox.x0 - dims.x0):int(line.bbox.x1 - dims.x0),
                    
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
        if len(c1_h_lines) >= 2*len(h_lines):
            return None
        
        #Filter line breaks out of low density tables
        self.logger.debug(f"Found line candidates - {h_lines}")
        line_width = np.max([h[1] for h in h_lines])
        if line_width > 4:
            self.logger.debug("Filtering lines from low density table")
            h_lines = [dims.y0]  + [h[0] + h[1]/2 + dims.y0 for h in h_lines if h[1] >= 3] + [dims.y1]
        else:
            h_lines = [dims.y0] + [h[0] + h[1]/2 + dims.y0 for h in h_lines] + [dims.y1]

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

        vertical_array = np.zeros(arr.shape)
        vertical_array = arr.sum(axis=0) == 0

        #Calculate all of the possible vertical lines
        v_lines = []
        current_run = -1
        current_run_length = 0
        for i,v in enumerate(vertical_array):
            if v > 0.5:
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

        v_lines = [dims.x0] + [v[0] + v[1]/2 + dims.x0 for v in v_lines] + [dims.x1]

        # ah = np.repeat(horizontal_array[:,np.newaxis], arr.shape[1], axis=1)
        # av = np.repeat(vertical_array[np.newaxis,:], arr.shape[0], axis=0)
        # fig = plt.imshow(5*(ah + av) + arr)
        # fig.show()

        table = [TableExtractorStrategy.TableParts.TABLE, dims.clone()]
        parts = []
        for i in range(len(h_lines) - 1):
            parts.append(
                [TableExtractorStrategy.TableParts.ROW, Bbox(dims.x0, h_lines[i], dims.x1, h_lines[i+1], dims.page_width, dims.page_height)]
            )

        for i in range(len(v_lines) - 1):
            parts.append(
                [TableExtractorStrategy.TableParts.COLUMN, Bbox(v_lines[i], dims.y0, v_lines[i+1], dims.y1, dims.page_width, dims.page_height)]
            )

        return (table, parts)