import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from plotly.graph_objects import Figure

from ..elements.bbox import Bbox
from ..elements.element import LayoutElement, LayoutElementGroup
from ..elements.image import ImageElement, ImageType
from ..elements.section import PageSection
from ..elements.table import Table
from ..utils.layout_graph import LayoutGraph
from ..utils.render_pages import add_text_to_figure
from .processor import Processor


class ReadingOrderProcessor(Processor):
    """Infers the correct reading order for all elements on a page. 

    The ReadingOrderProcessor analyses each section of a page independently and uses a 
    combination of heuristics to order elements within each, before creating an overall
    ordering of section.

    Requires: ["page_bounds", "elements", "image_elements"]
    Optional: ["tables"]
    Generates: ["elements"]
    """

    name: str = "reading-order"

    def __init__(self, log_level: int = logging.INFO):
        super().__init__(ReadingOrderProcessor.name, log_level=log_level)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (["page_bounds", "elements", "image_elements"], ['tables'])

    def generates(self) -> List[str]:
        return ['elements']

    def _elements_to_groups(self, page_bound: Bbox, elements: List[LayoutElement]) -> List[LayoutElementGroup]:
        """Order items within a section.

        Greedily orders items in a section starting from the top left and pushing downwards.
        Halts whenever a switch from central/single column to multicolumn occurs (or vice versa) and
        builds next column rightwards.
        Assume that this will correctly order items *within* a block/column of text but won't correctly
        order the blocks/columns themselves.

        Args:
            page_bound (Bbox): Bounding box of page
            elements (List[LayoutElement]): Elements to order

        Returns:
            _type_: A list of grouped items, assume reading order is correct within each group
        """
        self.logger.debug("Ordering %d elements", len(elements))
        elements.sort(key=lambda e: e.bbox.y0*100 + e.bbox.x0)
        page_width = page_bound.width()
        page_center = page_bound.center()

        columns: List[LayoutElementGroup] = []
        is_column_open: List[bool] = []
        for e in elements:
            used = False
            self.logger.debug(e)

            element_is_centered = abs(e.bbox.center().x - page_center.x) < 10
            element_is_full_page = e.bbox.width() / page_width > 0.6

            for i, c in enumerate(columns):
                if not is_column_open[i]:
                    continue

                col_is_full_age = c.bbox.width() / page_width > 0.6
                col_is_centered = abs(c.bbox.center().x - page_center.x) < 10

                col_and_element_left_aligned = (abs(c.bbox.x0 - e.bbox.x0) <
                                                2 and e.bbox.height() < 15)

                col_element_vertical_distance = e.bbox.y0 - c.bbox.y1
                col_element_x_overlap = c.bbox.x_overlap(e.bbox, 'first')
                element_col_x_overlap = c.bbox.x_overlap(e.bbox, 'second')
                append = False

                self.logger.debug(
                    "dy: %f, col: %f, block: %f, col_full_page: %f, el_full_page: %d, col_centered: %d, el_centered: %d",
                    col_element_vertical_distance, col_element_x_overlap, element_col_x_overlap,
                    col_is_full_age, element_is_full_page,
                    col_is_centered, element_is_centered)

                stop = False
                # If element starts above column end and the majority of the element overlaps
                # with it then merge
                if col_element_vertical_distance < 0:
                    if element_col_x_overlap > 0.8:
                        self.logger.debug(
                            "Appending as elements are overlapping")
                        append = True

                # Break between column/full page elements
                if not col_and_element_left_aligned and (
                    (col_is_full_age and not element_is_full_page) or
                        (element_is_full_page and not col_is_full_age)):
                    self.logger.debug(
                        "Won't merge as switch between column and full page")
                    stop = True

                # Break between centered and non centered elements
                if not col_and_element_left_aligned and (
                    (col_is_centered and not element_is_centered)
                        or (element_is_centered and not col_is_centered)
                ):
                    self.logger.debug(
                        "Wont merge as break between centered and non-centered")
                    stop = True

                # Merge if it's within ~2 lines and aligned
                # Don't merge if column starts to the right of the element center or element is to right of column center
                if not stop and not append and c.bbox.x0 < e.bbox.center().x and e.bbox.x0 < c.bbox.center().x:
                    if abs(col_element_vertical_distance) < 30:
                        if col_element_x_overlap > (0.1 if not col_is_full_age else 0.5):
                            self.logger.debug("Appending as has x overlap")
                            append = True
                    elif abs(col_element_vertical_distance) < 30:
                        if col_element_x_overlap > 0.6:
                            append = True

                if append:
                    c.append(e)
                    used = True
                    self.logger.debug("Appended")
                    break
                elif col_element_x_overlap > 0.1:
                    is_column_open[i] = False
                    self.logger.debug("Closing column")

            if not used:
                columns.append(
                    LayoutElementGroup(items=[e], title="Column")
                )
                is_column_open.append(True)
                self.logger.debug("Creating new column")

        # Merge overlapping columns
        remove_cols = set()
        for i, col_i in enumerate(columns):
            if i in remove_cols:
                continue
            for j, col_j in enumerate(columns):
                if i == j or j in remove_cols:
                    continue
                if col_i.bbox.overlap(col_j.bbox, 'min') > 0.5:
                    col_i.merge(col_j)
                    remove_cols.add(j)

        columns = [c for i, c in enumerate(columns) if i not in remove_cols]
        if len(remove_cols) > 0:
            self.logger.debug("Removing columns %s", str(remove_cols))

        columns.sort(key=lambda c: round(c.bbox.y0/10)*1000 + c.bbox.x0)
        self.logger.debug("Found %d columns", len(columns))

        return columns

    def _left_to_right_tree_sort(self, elements: Sequence[LayoutElement], page_bound: Bbox) -> List[LayoutElement]:
        """Sort elements based on a left-to-right tree. Backtracking whenever a new line would x-intersect
        a previous unused column.
        
        E.g.
        ::
        
                [a] [b]
                [c]
                [  d  ]
                [ e ] [ f ]
                      [ g ]
                  [  h  ]
        
        would sort as [a, c, b, d, e, f, g, h]. Uses the LayoutGraph adjancency to do this efficiently

        Args:
            elements (List[LayoutElement]): Elements to sort
            page_bound (Bbox): bounding box of the page

        Returns:
            List[LayoutElement]: The same elements in new order
        """

        # Within each section, do left-to-right, depth-first traversal of elements
        sorted_elements: List[LayoutElement] = []
        layout_graph = LayoutGraph(page_bound, elements)

        backtrack: List[LayoutGraph.Node] = []
        used = set([0])
        node: Optional[LayoutGraph.Node] = layout_graph.nodes[0]
        while node:

            # Can we go down
            if len(node.down) > 0:
                
                # Are downward nodes already used
                children = [layout_graph.get_node(
                    n) for n in node.down if n[0] not in used]
                
                if len(children) > 0:
                    # Sort left-to-right
                    children.sort(key=lambda c: c.element.bbox.x0)

                    # Are there unused nodes which interest with this one
                    do_backtrack = any(
                        layout_graph.get_node(u) in backtrack for u in children[0].up
                    )

                    # Nope - lets add the next element to the list and the
                    # continue to push downwards
                    if not do_backtrack:
                        sorted_elements += children[0].element #type:ignore
                        node = children[0]
                        used.add(node.node_id)
                        backtrack += reversed(children[1:])
                        continue

            # Apparently we need to backtrack - unwind current backtrack
            # queue until we find the first unused node
            if len(backtrack) > 0:
                node = backtrack.pop()
                while node.node_id in used and len(backtrack) > 0:
                    node = backtrack.pop()
                    if len(backtrack) == 0 and node.node_id in used:
                        node = None
                        break
                if node and node.node_id not in used:
                    sorted_elements += node.element  # type:ignore
                    used.add(node.node_id)
                    continue

            # If we hit this point we've processed all nodes
            break
        
        return sorted_elements


    def _order_groups_and_flatten(self, page_bound: Bbox, columns: Sequence[LayoutElementGroup]) -> List[LayoutElement]:
        """Take element groups and order across the full section

        Args:
            page_bound (Bbox): Page bound
            columns (Sequence[LayoutElementGroup]): Groups of elements, assume correct ordering already established
                within group

        Returns:
            List[LayoutElement]: All elements correctly ordered and flattened
        """

        self.logger.debug("Ordering %d element groups", len(columns))
        page_width = page_bound.width()
        sections: List[List[LayoutElementGroup]] = []
        current_section: List[LayoutElementGroup] = []
        is_full = None
        for element in columns:
            c_is_full = element.bbox.width() / page_width > 0.5
            if is_full is not None and c_is_full != is_full:
                sections.append(current_section)
                current_section = [element]
            else:
                current_section.append(element)
            is_full = c_is_full
        if len(current_section) > 0:
            sections.append(current_section)
            
        full_sorted_elements = []
        for section in sections:
            full_sorted_elements += self._left_to_right_tree_sort(section, page_bound)

        return full_sorted_elements


    def _flow_content(self, page_bound: Bbox, sections: List[PageSection], global_elements: List[ImageElement], tables: List[Table]) -> List[PageSection]:
        default_sections = [s for s in sections if s.default]
        other_sections = [s for s in sections if not s.default]

        # type:ignore
        global_elements: Sequence[LayoutElement] = global_elements + tables

        used_global_elements = set()

        for o_section in other_sections:
            self.logger.debug("Ordering section %s", o_section)
            
            in_line_elements = []
            out_of_line_elements = []
            for i, element in enumerate(global_elements):
                if i in used_global_elements:
                    continue
                if element.bbox.overlap(o_section.bbox, 'first') > 0.9:
                    overlap = 0.0
                    for block in o_section.items:
                        overlap += element.bbox.overlap(block.bbox, 'first')
                    if overlap > 0.2:
                        out_of_line_elements.append(
                            PageSection(element.bbox, [element]))
                    else:
                        in_line_elements.append(element)
                    used_global_elements.add(i)

            element_groups = self._elements_to_groups(
                page_bound, o_section.items + in_line_elements)  # type:ignore
            sorted_elements = self._order_groups_and_flatten(
                page_bound, element_groups + out_of_line_elements)
            o_section.items = sorted_elements

            # Insert into a default section - these will always cover the full page so there must
            # be a correct section to insert it into
            best_section: Tuple[PageSection, float] = (default_sections[0], 0.)
            for d_section in default_sections:
                overlap = o_section.bbox.overlap(d_section.bbox, 'first') > 0.5
                if overlap > best_section[1]:
                    best_section = (d_section, overlap)
                    
            best_section[0].append(o_section, update_bbox=False)

        self.logger.debug("Finished ordering non-default sections")

        complete_sections: List[PageSection] = []
        for d_section in default_sections:
            self.logger.debug("Ordering section %s", str(d_section))

            in_line_elements = []
            out_of_line_elements = []
            for i, element in enumerate(global_elements):
                if i in used_global_elements:
                    continue

                if element.bbox.overlap(d_section.bbox, 'first') > 0.9:
                    if isinstance(element, ImageElement) and (element.bbox.width(norm=True) > 0.6 or element.bbox.height(norm=True) > 0.6):
                        out_of_line_elements.append(
                            PageSection(element.bbox, [element]))
                        used_global_elements.add(i)
                        continue

                    overlap = 0
                    for block in d_section.items:
                        overlap += element.bbox.overlap(block.bbox, 'first')
                    if overlap > 0.2:
                        self.logger.debug(
                            "Assigning %s as out of line image in section", str(element))
                        out_of_line_elements.append(
                            PageSection(element.bbox, [element]))
                    else:
                        self.logger.debug(
                            "Assigning %s as inline image", str(element))
                        in_line_elements.append(element)
                    used_global_elements.add(i)

            element_groups = self._elements_to_groups(
                page_bound, d_section.items + in_line_elements)  # type:ignore
            sorted_elements = self._order_groups_and_flatten(
                page_bound, element_groups + out_of_line_elements)
            complete_sections.append(PageSection(
                items=sorted_elements, bbox=d_section.bbox, default=True))

        # Merge images with sections
        for i, element in enumerate(global_elements):
            if i not in used_global_elements:
                complete_sections.append(PageSection(element.bbox, [element]))

        return complete_sections

    def _process(self, data: Any) -> Any:
        for pn, page_bound, elements, images, tables in self.get_page_data(data):
            if not tables:
                tables = []
            elements = self._flow_content(
                page_bound, elements, images[ImageType.PRIMARY], tables)
            data['elements'][pn] = elements

        self.logger.debug("Finished computing layout")

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):

        colours = {
            "TextBlock": "Black",
            "ImageElement": "DarkRed",
            "Table": "Aqua",
        }

        item_order = 1

        def recursive_add(colours, fig, e, item_order):
            if isinstance(e, PageSection):
                for i in e:
                    item_order = recursive_add(colours, fig, i, item_order)
            elif type(e).__name__ in colours:
                add_text_to_figure(fig, e.bbox.center(),
                                   colours[type(e).__name__], item_order)
                item_order += 1
            elif isinstance(e, LayoutElementGroup):
                for item in e:
                    item_order = recursive_add(colours, fig, item, item_order)
            elif isinstance(e, list) or isinstance(e, LayoutElementGroup):
                for item in e:
                    item_order = recursive_add(colours, fig, item, item_order)

            return item_order

        for element in data['elements'][page_number]:
            item_order = recursive_add(colours, fig, element, item_order)
