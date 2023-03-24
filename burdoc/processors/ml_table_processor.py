
import logging
from typing import List, Any, Dict
from enum import Enum, auto
import numpy as np

from .processor import Processor

from ..elements.layout_objects import *
from ..elements.bbox import Bbox

from ..table_strategies.detr_table_strategy import DetrTableStrategy
from ..table_strategies.table_extractor_strategy import TableExtractorStrategy
from ..elements.table import Table

from plotly.graph_objects import Figure


class MLTableProcessor(Processor):

    threadable: bool = False

    class Strategies (Enum):
        DETR = auto()

    strategy: TableExtractorStrategy

    def __init__(self, logger: logging.Logger, strategy: Strategies=Strategies.DETR):
        super().__init__('tables', logger)

        if strategy == MLTableProcessor.Strategies.DETR:
            self.strategy_type = DetrTableStrategy

    def initialise(self):
        self.strategy = self.strategy_type(self.logger)
        return super().initialise()

    def requirements(self) -> List[str]:
        return self.strategy_type.requirements() + ['text']
    
    def generates(self) -> List[str]:
        return ['tables', 'text']
    
    def process(self, data: Any) -> Table:
        reqs = self.strategy.requirements()
        fields = {r:data[r] for r in self.strategy.requirements()}
        fields['page_numbers'] = list(data[reqs[0]].keys())
        extracted_tables = self.strategy.extract_tables(**fields)

        data['tables'] = {p:[] for p  in fields['page_numbers']}

        if len(extracted_tables) == 0:
            return
        
        for page in extracted_tables:
            page_tables = []
            for table_bbox, structure in extracted_tables[page]:
                row_headers = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.RowHeader]
                rows = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.Row]
                col_headers = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.ColumnHeader]
                cols = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.Column]
            
                rs = col_headers + rows
                cs = row_headers + cols
                
                merges  = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.SpanningCell]

                if len(cols) < 2:
                    continue

                page_tables.append(Table(table_bbox[1], [[[] for _ in cs] for _ in rs], 
                                         row_boxes=rs, col_boxes=cs, merges=merges))

            bad_lines = np.array([0 for _ in page_tables])
            used_text = np.array([-1 for _ in data['text'][page]])
            for line_index,line in enumerate(data['text'][page]):
                shrunk_bbox = line.bbox.clone()
                # shrunk_bbox.x0 += 0
                # shrunk_bbox.x1 -= 0
                shrunk_bbox.y0 += 2
                if shrunk_bbox.height() > 8:
                    shrunk_bbox.y1 -= 5
                #print(line)
                #print(line.bbox, shrunk_bbox)
                for table_index,table in enumerate(page_tables):
                    table_line_x_overlap = shrunk_bbox.x_overlap(table.bbox, 'first')
                    table_line_y_overlap = shrunk_bbox.y_overlap(table.bbox, 'first')
  
                    if table_line_x_overlap > 0.93 and table_line_y_overlap > 0.93:

                        candidate_row_index = -1
                        for row_index,row in enumerate(table.row_boxes):
                            #print("row", row_index, shrunk_bbox.y_overlap(row[1], 'first'), row[1])
                            if shrunk_bbox.overlap(row[1], 'first') > 0.85:
                                candidate_row_index = row_index
                                break
                        if candidate_row_index < 0:
                            if table_line_x_overlap > 0.99 and table_line_y_overlap > 0.99:
                                bad_lines[table_index] += 10
                            else:
                                bad_lines[table_index] += 1   
                            continue

                        candidate_col_index = -1
                        for col_index,col in enumerate(table.col_boxes):
                            #print("col", col_index, shrunk_bbox.x_overlap(col[1], 'first'), row[1])
                            if line.bbox.overlap(col[1], 'first') > 0.85:
                                candidate_col_index = col_index
                                break
                        if candidate_col_index < 0:
                            if table_line_x_overlap > 0.99 and table_line_y_overlap > 0.99:
                                bad_lines[table_index] += 10
                            else:
                                bad_lines[table_index] += 1
                            continue
                        
                        used_text[line_index] = table_index
                        table._cells[candidate_row_index][candidate_col_index].append(line)
                        continue
                        
                    elif table_line_x_overlap > 0.5 and table_line_y_overlap > 0.5:
                        bad_lines[table_index] += 10

                    elif table_line_x_overlap > 0.1 and table_line_y_overlap > 0.1:
                        bad_lines[table_index] += 1

            for line_index,z in enumerate(zip(page_tables, bad_lines)):
                table = z[0]
                bl = z[1]
                if bl >= 3:
                    used_text[used_text == line_index] = -1
                    continue

                data['tables'][page].append(table)

            keep_text = []
            for line,u in zip(data['text'][page], used_text):
                if u >= 0:
                    continue
                keep_text.append(line)

            data['text'][page] = keep_text   

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

            for rb in t.row_boxes:
                add_rect(fig, rb[1], colours['row'])
            for cb in t.col_boxes:
                add_rect(fig, cb[1], colours['col'])
            for sb in t.merges:
                add_rect(fig, sb[1], colours['merges'])



        fig.add_scatter(x=[None], y=[None], name="Table", line=dict(width=3, color=colours["table"]))
