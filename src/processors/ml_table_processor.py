
import logging
from typing import List, Any, Dict
from enum import Enum, auto
import numpy as np

from .processor import Processor

from ..elements.layout_objects import *
from ..elements.bbox import Bbox

from ..table_strategies.detr_table_strategy import DetrTableStrategy
from ..table_strategies.rules_table_strategy import RulesTableStrategy
from ..table_strategies.table_extractor_strategy import TableExtractorStrategy
from ..elements.table import Table

from plotly.graph_objects import Figure


class MLTableProcessor(Processor):

    class Strategies (Enum):
        DETR = auto()

    strategy: TableExtractorStrategy

    def __init__(self, logger: logging.Logger, strategy: Strategies=Strategies.DETR):
        super().__init__('tables', logger)

        if strategy == MLTableProcessor.Strategies.DETR:
            self.strategy = DetrTableStrategy(self.logger)
        else:
            self.logger.error("Unknown table processing strategy")

    @staticmethod
    def requirements() -> List[str]:
        return ['page_images', 'text']
    
    @staticmethod
    def generates() -> List[str]:
        return ['tables', 'text']
    
    def process(self, data: Any) -> Table:
        reqs = self.strategy.requirements()
        fields = {r:data[r] for r in self.strategy.requirements()}
        fields['page_numbers'] = list(data[reqs[0]].keys())
        found_tables = self.strategy.extract_tables(**fields)

        data['tables'] = {p:[] for p  in fields['page_numbers']}

        if len(found_tables) == 0:
            return
        
        for page in found_tables:
            tabs = []
            for table_bbox, structure in found_tables[page]:
                header_rows = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.RowHeader]
                rows = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.Row]
                header_cols = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.ColumnHeader]
                cols = [s for s in structure if s[0] == TableExtractorStrategy.TableParts.Column]
            
                rs = header_rows + rows
                cs = header_cols + cols

                if len(cs) < 2:
                    continue

                tabs.append([Table(table_bbox[1], [[[] for _ in cs] for _ in rs]), rs, cs])

            bad_lines = np.array([0 for _ in tabs])
            used_text = np.array([-1 for _ in data['text'][page]])
            for line_index,line in enumerate(data['text'][page]):
                for table_index,table in enumerate(tabs):
                    x_overlap = line.bbox.x_overlap(table[0].bbox, 'first')
                    y_overlap = line.bbox.y_overlap(table[0].bbox, 'first')
                    overlap = x_overlap * y_overlap
                    if x_overlap > 0.95 and y_overlap > 0.95:
                        r_index = -1
                        for row_index,row in enumerate(table[1]):
                            if line.bbox.overlap(row[1], 'first') > 0.95:
                                r_index = row_index
                                break
                        if r_index < 0:
                            continue

                        c_index = -1
                        for col_index,col in enumerate(table[2]):
                            if line.bbox.overlap(col[1], 'first') > 0.95:
                                c_index = col_index
                                break
                        if c_index < 0:
                            continue
                        
                        used_text[line_index] = table_index
                        table[0]._cells[r_index][c_index].append(line)
                        continue
                        
                    elif overlap > 0.2:
                        bad_lines[table_index] += 1

            for line_index,z in enumerate(zip(tabs, bad_lines)):
                line = z[0]
                bl = z[1]
                if bl >= 3:
                    used_text[used_text == line_index] = -1
                    continue

                data['tables'][page].append(line[0])

            keep_text = []
            for line,u in zip(data['text'][page], used_text):
                if u >= 0:
                    continue
                keep_text.append(line)

            data['text'][page] = keep_text   

    @staticmethod
    def add_generated_items_to_fig(page_number:int, fig: Figure, data: Dict[str, Any]):
        colours = {
            "table":"Cyan",
            "cell":"LightGrey"
        }

        def add_rect(fig, bbox, colour):
            fig.add_shape(
                type='rect', xref='x', yref='y', opacity=0.6,
                x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
                line=dict(color=colour, width=3)
            )

        for t in data['tables'][page_number]:
            add_rect(fig, t.bbox, colours["table"])

        fig.add_scatter(x=[None], y=[None], name="Table", line=dict(width=3, color=colours["table"]))
