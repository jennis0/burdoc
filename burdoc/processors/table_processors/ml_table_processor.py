import logging
from enum import Enum, auto
from typing import Any, Dict, List, Tuple

import numpy as np
from plotly.graph_objects import Figure

from ...elements import Table, TableParts
from ..processor import Processor
from .detr_table_strategy import DetrTableStrategy
from .table_extractor_strategy import TableExtractorStrategy


class MLTableProcessor(Processor):
    """Wrapper for ML models to detect tables. Separated from rules based processor as
    it can only be run single-threaded.  

    Requires: ['text_elements'] and additional requirements from specific strategy  
    Optional: []  
    Generates: ['tables', 'text_elements']
    """

    threadable: bool = False
    name: str = "ml-tables"

    class Strategies (Enum):
        DETR = auto()

    strategy: TableExtractorStrategy

    def __init__(self, strategy: Strategies=Strategies.DETR, log_level: int=logging.INFO):
        super().__init__(MLTableProcessor.name, log_level=log_level)
        self.log_level = log_level

        if strategy == MLTableProcessor.Strategies.DETR:
            self.strategy_type = DetrTableStrategy

    def initialise(self):
        self.strategy = self.strategy_type(self.log_level)
        return super().initialise()

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (self.strategy_type.requirements() + ['text_elements'], [])
    
    def generates(self) -> List[str]:
        return ['tables', 'text_elements']
    
    def _process(self, data: Dict[str, Any]):
        required_fields = self.strategy.requirements()
        fields = {r:data[r] for r in self.strategy.requirements()}
        fields['page_numbers'] = list(data[required_fields[0]].keys())
        
        data['tables'] = {p:[] for p  in fields['page_numbers']}
        
        extracted_tables = self.strategy.extract_tables(**fields)

        if len(extracted_tables) == 0:
            return
        
        for page, list_of_table_parts in extracted_tables.items():

            #Create a list of table candidates for the page
            page_table_candidates: List[Table] = []
            for table_parts in list_of_table_parts:
                table_bbox  = table_parts[0][1]
                row_headers = [s for s in table_parts[1:] if s[0] == TableParts.ROWHEADER]
                rows        = [s for s in table_parts[1:] if s[0] == TableParts.ROW]
                col_headers = [s for s in table_parts[1:] if s[0] == TableParts.COLUMNHEADER]
                cols        = [s for s in table_parts[1:] if s[0] == TableParts.COLUMN]
                #merges      = [s for s in table_parts[1:] if s[0] == TableParts.SPANNINGCELL]  
            
                all_rows = col_headers + rows
                all_cols = row_headers + cols
                
                if len(all_cols) < 2:
                    continue
                
                if len(all_rows) < 1:
                    continue
                
                all_rows.sort(key=lambda r: r[1].y0)
                all_cols.sort(key=lambda r: r[1].x0)

                page_table_candidates.append(Table(table_bbox, all_rows, all_cols))
                
    
            bad_lines = np.array([0 for _ in page_table_candidates])
            used_text = np.array([-1 for _ in data['text_elements'][page]])
            
            for line_index,line in enumerate(data['text_elements'][page]):
                shrunk_bbox = line.bbox.clone()
                shrunk_bbox.y0 += 2
                if shrunk_bbox.height() > 8:
                    shrunk_bbox.y1 -= 5
  
                for table_index,candidate_table in enumerate(page_table_candidates):
                    
                    if not candidate_table.row_boxes or not candidate_table.col_boxes:
                        continue
                    
                    table_line_x_overlap = shrunk_bbox.x_overlap(candidate_table.bbox, 'first')
                    table_line_y_overlap = shrunk_bbox.y_overlap(candidate_table.bbox, 'first')
                      
                    if table_line_x_overlap > 0.93 and table_line_y_overlap > 0.93:

                        #Find correct row
                        candidate_row_index = -1
                        for row_index,row in enumerate(candidate_table.row_boxes):
                            if shrunk_bbox.overlap(row[1], 'first') > 0.85:
                                candidate_row_index = row_index
                                break
                        #If no correct row, punish table candiate
                        if candidate_row_index < 0:
                            if table_line_x_overlap > 0.99 and table_line_y_overlap > 0.99:
                                bad_lines[table_index] += 10
                            else:
                                bad_lines[table_index] += 1   
                            continue

                        #Find correct column
                        candidate_col_index = -1
                        for col_index,col in enumerate(candidate_table.col_boxes):
                            if line.bbox.overlap(col[1], 'first') > 0.85:
                                candidate_col_index = col_index
                                break
                        #If no correct row, punish table candidate
                        if candidate_col_index < 0:
                            if table_line_x_overlap > 0.99 and table_line_y_overlap > 0.99:
                                bad_lines[table_index] += 10
                            else:
                                bad_lines[table_index] += 1
                            continue
                        
                        #Note which table text has been assigned too
                        used_text[line_index] = table_index
                        #Add text to table
                        candidate_table.cells[candidate_row_index][candidate_col_index].append(line)
                        continue
                        
                    #If table overlaps with none-table text, punish table
                    if table_line_x_overlap > 0.5 and table_line_y_overlap > 0.5:
                        bad_lines[table_index] += 10
                    elif table_line_x_overlap > 0.1 and table_line_y_overlap > 0.1:
                        bad_lines[table_index] += 1

            #Check badness of tables and either accept them or unmark any used text
            for line_index,tables_and_bad_line_count in enumerate(zip(page_table_candidates, bad_lines)):
                table = tables_and_bad_line_count[0]
                bad_line_count = tables_and_bad_line_count[1]
                                
                if bad_line_count >= 11:
                    used_text[used_text == line_index] = -1
                    continue
                
                remove_rows = set()
                remove_cols = set()
                for i, iter_row in enumerate(table.cells):
                    count = sum(len(cell) for cell in iter_row)
                    if count == 0:
                        remove_rows.add(i)
                        
                for j in range(len(table.cells[0])):
                    count = sum(len(row[j]) for row in table.cells)
                    if count == 0:
                        remove_cols.add(j)
                        
                table.cells = [
                    [cell for j,cell in enumerate(row) if j not in remove_cols] \
                        for i, row in enumerate(table.cells) if i not in remove_rows]

                data['tables'][page].append(table)

            #Filter text that has been inserted into tables
            data['text_elements'][page] = [t for t,is_used in zip(data['text_elements'][page], used_text) \
                                                if is_used < 0]

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

            for row_box in t.row_boxes:
                add_rect(fig, row_box[1], colours['row'])
            for col_box in t.col_boxes:
                add_rect(fig, col_box[1], colours['col'])
            for merged_box in t.merges:
                add_rect(fig, merged_box[1], colours['merges'])



        fig.add_scatter(x=[None], y=[None], name="Table", line=dict(width=3, color=colours["table"]))
