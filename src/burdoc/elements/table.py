from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# from ..table_strategies.table_extractor_strategy import TableExtractorStrategy
from .bbox import Bbox
from .element import LayoutElement


class TableParts(Enum):
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
                 row_boxes: List[Tuple[TableParts, Bbox]],
                 col_boxes: List[Tuple[TableParts, Bbox]],
                 merge_boxes: List[Tuple[TableParts, Bbox]]
                 ):
        """Creates a Table element

        Args:
            bbox (Bbox): Bounding box of the the table
            row_boxes (List[Tuple[TableParts, Bbox]]): Bounding box and descriptor of each row - 
                use TableParts.COLUMNHEADER to indicate a row used as a header
            col_boxes (List[Tuple[TableParts, Bbox]]): Bounding box and descriptor of each column - 
                use TableParts.ROWHEADER to indicate a column used as a header
        """
        super().__init__(bbox, title='Table')
        self.cells: List[List[List[LayoutElement]]] = \
            [[[] for _ in range(len(col_boxes))]
             for _ in range(len(row_boxes))]
        self.row_boxes = row_boxes
        self.col_boxes = col_boxes
        self.merges = merge_boxes
        self.col_headers = [i for i, s in enumerate(
            col_boxes) if s[0] == TableParts.ROWHEADER]
        self.row_headers = [i for i, s in enumerate(
            row_boxes) if s[0] == TableParts.COLUMNHEADER]

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
