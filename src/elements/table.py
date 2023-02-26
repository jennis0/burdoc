from typing import List, Any, Tuple, Dict

from .element import LayoutElement
from .bbox import Bbox


class Table(LayoutElement):

    def __init__(self, 
                 bbox: Bbox, 
                 cells: List[List[Any]], 
                 row_headers: List[Any]=None, 
                 col_headers: List[Any]=None, 
                 merges: Dict[Tuple[int, int], List[Tuple[int,int]]]=None
    ):
        super().__init__(bbox)
        self._cells = cells
        self.row_headers = row_headers
        self.col_headers = col_headers
        self.merges = merges

    def _get_cell(self, row:int, col: int):
        val = {'c':self._cells[row][col]}
        if self.row_headers:
            val['rh'] = self.row_headers[row]
        if self.col_headers:
            val['ch'] = self.col_headrs[col]

        return val

    def get_cell(self, row: int, col: int):
        val = {}
        if (row, col) in self.merges:
            for r,c in self.merges[(row, col)]:
                cell = self._get_cell(r, c)
                for k in cell:
                    if k not in val:
                        val[k] = [cell[k]]
                    else:
                        val[k].append(cell[k])
        else:
            val = self._get_cell(row, col)

        return val

    def to_html(self):
        text = "<table>"
        if self.col_headers:
            headers = [f"<th>{ch.to_html()}</th>" for rh in self.col_headers]
            text += f"<tr>{''.join(headers)}</tr>"

        for i,row in enumerate(self._cells):
            cells = []
            if self.row_headers:
                cells.append(f"<th>{self.row_headers[i]}</th>")
            cells += [f"<td>{r}</td>" for r in row]
            text += f"<tr>{''.join(cells)}</tr>"

        text += "</table>"
        return text
    
    def to_json(self):
        return {
            'bbox':self.bbox.to_json(),
            'rh':[r.to_json() for r in self.row_headers],
            'ch':[c.to_json() for c in self.col_headers],
            'cells':[c.to_json() for c in self._cells],
            'merges':self.merges
        }
    
    def __str__(self):
        return f"<Table Id={self.id[:8]}... Bbox={str(self.bbox)}>"
            
        