import logging
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Type, cast

import numpy as np
from plotly.graph_objects import Figure

from ...elements import Bbox, LayoutElement, Table, TablePart
from ...utils.render_pages import add_rect_to_figure
from ..processor import Processor
from .detr_table_strategy import DetrTableStrategy
from .rules_table_strategy import RulesTableStrategy
from .table_extractor_strategy import TableExtractorStrategy


class MLTableProcessor(Processor):
    """Wrapper for ML models to detect tables. Separated from rules based processor as
    it can only be run single-threaded.  

    Requires: ['text_elements'] and additional requirements from specific strategy  
    Optional: []  
    Generates: ['tables', 'text_elements']
    """

    threadable: bool = False
    expensive: bool = True
    name: str = "ml-tables"

    class Strategy (Enum):
        """List of possible ML table finding strategies

        Currently implemented:
        * DETR: DETR Using Microsoft Table Transformers  gi

        """
        DETR = auto()
        RULES = auto()

    strategies: Dict[Strategy, Type[TableExtractorStrategy]] = {
        Strategy.DETR: DetrTableStrategy,
        Strategy.RULES: RulesTableStrategy
    }

    strategy: TableExtractorStrategy

    def __init__(self, strategy: Strategy = Strategy.DETR,
                 input_field: str = 'text_elements', log_level: int = logging.INFO):
        super().__init__(MLTableProcessor.name, log_level=log_level)
        self.log_level = log_level
        self.strategy_type = self.strategies[strategy]
        self.input_field = input_field
        self.using_elements = input_field == 'elements'
        self.bad_element_threshold = 10

    def initialise(self):
        self.strategy = self.strategy_type(self.log_level)
        return super().initialise()

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (self.strategy_type.requirements() + ['text_elements'], [])

    def generates(self) -> List[str]:
        return ['tables', self.input_field] + self.strategy_type.generates()

    def _get_cell_index_for_bbox(self, table: Table, bbox: Bbox) -> Optional[Tuple[List[int], List[int]]]:
        """Gets the index of all rows and columns the bbox overlaps with.

        Args:
            table (Table): The table to test overlap against
            bbox (Bbox): The bboxto test overlap with

        Returns:
            Optional[Tuple[List[int], List[int]]]: Row indices and cell indices the line overlaps with. Returns None if
                the line doesn't overlap the table at all
        """

        table_line_x_overlap = bbox.x_overlap(
            table.bbox, 'first')
        table_line_y_overlap = bbox.y_overlap(
            table.bbox, 'first')

        if table_line_x_overlap > 0.9 and table_line_y_overlap > 0.9:

            # Find correct row
            overlapping_row_indices: List[int] = []
            for row_index, row in enumerate(table.row_boxes):
                if bbox.overlap(row[1], 'first') > 0.1:
                    overlapping_row_indices.append(row_index)
                    continue
                if len(overlapping_row_indices) >= 1:
                    break

            # Find correct column
            overlapping_col_indices: List[int] = []
            for col_index, col in enumerate(table.col_boxes):
                if bbox.overlap(col[1], 'first') > 0.1:
                    overlapping_col_indices.append(col_index)
                    continue
                if len(overlapping_col_indices) >= 1:
                    break

            return (overlapping_row_indices, overlapping_col_indices)

        return None

    def _check_if_in_spanning_cell(self, table: Table, cell_indices: Tuple[List[int], List[int]]) -> Optional[Tuple[List[int], List[int]]]:
        """Checks whether the passed indices are contained entirely within a single spanning cell. 

        Args:
            table (Table): Table to check against
            cell_indices (Tuple[List[int], List[int]]): The lists of row indices and column indices the element
                overlaps with

        Returns:
            Optional[Tuple[List[int], List[int]]]: The full indices of the spanning cell if found, otherwise None
        """

        spanning_cell = None
        for tsc in table.spanning_cells:
            this_row = True
            for row in cell_indices[0]:
                if row not in tsc[0]:
                    this_row = False
                    break

            if not this_row:
                continue

            this_col = True
            for col in cell_indices[1]:
                if col not in tsc[1]:
                    this_col = False
                    break

            if this_row and this_col:
                spanning_cell = tsc
                break

        return spanning_cell

    def _extract_tables(
        self, text: List[LayoutElement],
        list_of_table_parts: List[List[Tuple[TablePart, Bbox]]]
    ) -> Tuple[List[LayoutElement], List[Table]]:
        """Creates table from table parts and assigns elements to those tables.

        Args:
            text (List[LayoutElement]): Elements to be assigned to tables
            list_of_table_parts (List[List[Tuple[TablePart, Bbox]]]): Table parts from extraction strategy

        Returns:
            Tuple[List[LayoutElement], List[Table]]: Updated list of elements and found tables
        """

        # Create a list of table candidates for the page
        page_table_candidates: List[Table] = []
        for table_parts in list_of_table_parts:

            for tp in table_parts:
                print(tp)

            table = Table.from_table_parts(table_parts)

            if len(table.row_boxes) < 2 or len(table.col_boxes) < 2:
                continue

            page_table_candidates.append(table)

        bad_lines = np.array([0 for _ in page_table_candidates])
        used_text = np.array([-1 for _ in text])

        for line_index, line in enumerate(text):
            shrunk_bbox = line.bbox.clone()
            shrunk_bbox.x0 += 2
            shrunk_bbox.x1 -= 2
            shrunk_bbox.y0 += 2
            shrunk_bbox.y1 = max(shrunk_bbox.y0+1, shrunk_bbox.y1-5)

            for table_index, candidate_table in enumerate(page_table_candidates):

                if not candidate_table.row_boxes or not candidate_table.col_boxes:
                    continue

                cell_indices = self._get_cell_index_for_bbox(candidate_table, shrunk_bbox)

                if not cell_indices:
                    continue

                if len(cell_indices[0]) == 0 or len(cell_indices[1]) == 0:
                    bad_lines[table_index] += 1
                    continue

                spanning_cell = self._check_if_in_spanning_cell(table, cell_indices)

                if not spanning_cell:
                    candidate_table.cells[cell_indices[0][0]][cell_indices[1][0]].append(line)
                    used_text[line_index] = table_index

                    if len(cell_indices[0]) > 1 or len(cell_indices[1]) > 1:
                        bad_lines[table_index] += 1

                else:
                    candidate_table.cells[spanning_cell[0][0]][spanning_cell[1][0]].append(line)

        # Check badness of tables and either accept them or unmark any used text
        true_page_tables: List[Table] = []
        for line_index, tables_and_bad_line_count in enumerate(zip(page_table_candidates, bad_lines)):
            table = tables_and_bad_line_count[0]
            bad_line_count = tables_and_bad_line_count[1]

            if bad_line_count > self.bad_element_threshold or len(table.cells) == 0:
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
                [cell for j, cell in enumerate(
                    row) if j not in remove_cols]
                for i, row in enumerate(table.cells) if i not in remove_rows]

            true_page_tables.append(table)

        # Filter text that has been inserted into tables
        new_elements = [t for t, is_used in zip(text, used_text)
                        if is_used < 0]

        return new_elements, true_page_tables

    def _process(self, data: Dict[str, Any]):
        required_fields = self.strategy.requirements()
        fields = {r: data[r] for r in self.strategy.requirements()}
        fields['page_numbers'] = list(data[required_fields[0]].keys())

        if 'tables' not in data:
            data['tables'] = {p: [] for p in fields['page_numbers']}

        found_table_parts = self.strategy.extract_tables(fields)

        if self.using_elements:
            for page, page_section_table_parts in found_table_parts.items():
                elements = data[self.input_field]
                i = 0
                page_section_table_parts = cast(List[List[List[Tuple[TablePart, Bbox]]]], page_section_table_parts)
                for section_elements, list_of_table_parts in zip(elements, page_section_table_parts):
                    new_elements, tables = self._extract_tables(section_elements, list_of_table_parts)
                    data[self.input_field][page][i].items = new_elements
                    data["tables"][page] += tables
                    i += 1
        else:
            for page, list_of_table_parts in found_table_parts.items():
                new_elements, tables = self._extract_tables(data[self.input_field][page], list_of_table_parts)
                data[self.input_field][page] = new_elements
                data["tables"][page] = tables

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        colours = {
            "table": "Cyan",
            'row': "Grey",
            'row_header': 'DarkGrey',
            "col": "Grey",
            'col_header': 'DarkGrey',
            "merges": "Turquoise"
        }

        for table in data['tables'][page_number]:
            table = cast(Table, table)
            add_rect_to_figure(fig, table.bbox, colours["table"])

            for i, row_box in enumerate(table.row_boxes):
                if i in table.col_headers:
                    add_rect_to_figure(fig, row_box[1], colours['col_header'])
                else:
                    add_rect_to_figure(fig, row_box[1], colours['row'])
            for i, col_box in enumerate(table.col_boxes):
                if i in table.row_headers:
                    add_rect_to_figure(fig, col_box[1], colours['row_header'])
                else:
                    add_rect_to_figure(fig, col_box[1], colours['col'])
            for merged_box in table.merges:
                add_rect_to_figure(fig, merged_box[1], colours['merges'])

        fig.add_scatter(x=[None], y=[None], name="Table",
                        line=dict(width=3, color=colours["table"]))
        fig.add_scatter(x=[None], y=[None], name="Table Row/Column",
                        line=dict(width=3, color=colours["row"]))
        fig.add_scatter(x=[None], y=[None], name="Table Spanning Cell",
                        line=dict(width=3, color=colours["merges"]))

        fig.add_scatter(x=[None], y=[None], name="Table Header",
                        line=dict(width=3, color=colours["row_header"]))
