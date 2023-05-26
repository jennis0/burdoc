from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# from ..table_strategies.table_extractor_strategy import TableExtractorStrategy
from .bbox import Bbox
from .element import LayoutElement


class TablePart(Enum):
    """Enum defining the different parts of a table that can be extracted"""
    TABLE = 0
    COLUMN = 1
    ROW = 2
    COLUMNHEADER = 3
    ROWHEADER = 4
    SPANNINGCELL = 5


class Table(LayoutElement):
    """Representation of a table within the text.
    """

    def __init__(self,
                 bbox: Bbox,
                 row_boxes: List[Tuple[TablePart, Bbox]],
                 col_boxes: List[Tuple[TablePart, Bbox]],
                 spanning_cell_boxes: List[Tuple[TablePart, Bbox]]
                 ):
        """Creates a Table element

        Args:
            bbox (Bbox): Bounding box of the the table
            row_boxes (List[Tuple[TableParts, Bbox]]): Bounding box and descriptor of each row - 
                use TableParts.COLUMNHEADER to indicate a row used as a header
            col_boxes (List[Tuple[TableParts, Bbox]]): Bounding box and descriptor of each column - 
                use TableParts.ROWHEADER to indicate a column used as a header
            merge_boxes (List[Tuple[TableParts, Bbox]]): Bounding box and description of
                any spanning cells within the table
        """
        super().__init__(bbox, title='Table')
        self.cells: List[List[List[LayoutElement]]] = \
            [[[] for _ in range(len(col_boxes))]
             for _ in range(len(row_boxes))]
        self.row_boxes = row_boxes
        self.col_boxes = col_boxes
        self.merges = spanning_cell_boxes
        self.col_headers = [i for i, s in enumerate(
            col_boxes) if s[0] == TablePart.COLUMNHEADER]
        self.row_headers = [i for i, s in enumerate(
            row_boxes) if s[0] == TablePart.ROWHEADER]
        
        self.spanning_cells: List[Tuple[List[int], List[int]]] = []
        for scb in spanning_cell_boxes:
            scb_rows: List[int] = []
            scb_cols: List[int] = []
            for i,row in enumerate(self.row_boxes):
                if scb[1].overlap(row[1], 'first') > 0.1:
                    scb_rows.append(i)
            
            for i,col in enumerate(self.col_boxes):
                if scb[1].overlap(col[1], 'first') > 0.1:
                    scb_cols.append(i)
                    
            self.spanning_cells.append([(scb_rows, scb_cols)])

    @staticmethod
    def from_table_parts(table_parts: List[Tuple[TablePart, Bbox]]) -> Table:
        """Creates a table from a list of table parts. 
        
        If a TABLE part is provided, the overall table will use this Bbox, otherwise
        it takes the union of all passed row and column bboxes.

        Args:
            table_parts (List[Tuple[TableParts, Bbox]]): A list of tuple of the form
                TablePart, Bbox.

        Returns:
            Table: A created table. Note no check is done to ensure this is a
                sensible table
        """      
        table_part = [s for s in table_parts if s[0] == TablePart.TABLE]
        
        row_headers = [s for s in table_parts[1:]
                        if s[0] == TablePart.ROWHEADER]
        rows = [s for s in table_parts[1:] if s[0] == TablePart.ROW]
        col_headers = [s for s in table_parts[1:]
                        if s[0] == TablePart.COLUMNHEADER]
        cols = [s for s in table_parts[1:]
                if s[0] == TablePart.COLUMN]
        merges = [s for s in table_parts[1:] if s[0] == TablePart.SPANNINGCELL]

        all_rows = col_headers + rows
        all_cols = row_headers + cols

        all_rows.sort(key=lambda r: r[1].y0)
        all_cols.sort(key=lambda r: r[1].x0)
        
        if table_part:
            table_bbox = table_part[0][1]
        else:
            table_bbox = Bbox.merge([r[1] for r in all_rows] + [c[1] for c in all_cols])
        
        return Table(table_bbox, all_rows, all_cols, merges)

    def to_json(self, extras: Optional[Dict] = None, include_bbox: bool = False, **kwargs):
        if not extras:
            extras = {}

        extras['row_header_index'] = self.row_headers
        extras['col_header_index'] = self.col_headers
        json_cells: List[List[Any]] = []
        for row in self.cells:
            json_cells.append([])
            for col in row:
                json_cells[-1].append([l.to_json() for l in col])
        extras['cells'] = json_cells

        return super().to_json(extras=extras, include_bbox=include_bbox, **kwargs)

    def __str__(self):
        n_cells = sum([len(r) for r in self.cells])
        return f"<Table Id={self.element_id[:8]}... Bbox={str(self.bbox)} N_Cells={n_cells}>"
