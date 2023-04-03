import logging
import re
import roman
from typing import Any, Dict, List, Tuple, Union

from plotly.graph_objects import Figure

from ..elements.aside import Aside
from ..elements.element import LayoutElement
from ..elements.section import PageSection
from ..elements.textblock import TextBlock, TextBlockType
from ..elements.textlist import TextList, TextListItem
from ..utils.regexes import get_list_regex
from ..utils.render_pages import add_rect_to_figure, add_text_to_figure
from .processor import Processor


class ListProcessor(Processor):
    """The ListProcessor takes the correctly ordered layout elements 
    and identifies ordered and unordered lists

    **Requires:** ['elements']

    **Optional:** None

    **Generators:** ['elements', 'page_hierarchy']
    """

    name: str = "content"

    def __init__(self, log_level: int = logging.INFO):
        self.list_regex = get_list_regex()

        super().__init__(ListProcessor.name, log_level=log_level)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (['elements'], [])

    def generates(self) -> List[str]:
        return ['elements']

    def _get_list_index_from_match(self, match: re.Match) -> str:
        for group in match.groups():
            if group:
                return group
        return ""

    def _is_next_list_index(self, last_index: str, next_index: str) -> bool:
        if last_index == "\u2022":
            if next_index == "\u2022":
                return True
            return False

        last_is_num = str.isnumeric(last_index)
        next_is_num = str.isnumeric(next_index)
        if last_is_num != next_is_num:
            return False
        
        if last_is_num:
            return int(next_index) - int(last_index) == 1

        #Try to handle roman numerals
        if 'i' in last_index.lower() or 'i' in next_index.lower():
            try:
                last_as_roman = roman.fromRoman(last_index.upper())
                next_as_roman = roman.fromRoman(next_index.upper())
                return next_as_roman - last_as_roman == 1
            except roman.InvalidRomanNumeralError:
                pass
                
            if len(last_index) > 1 or len(next_index) > 1:
                return False
            
        if ord(next_index) - ord(last_index) == 1:
            return True

        return False

    def _create_list(self, list_items: List[Tuple[str, List[TextBlock]]]) -> Union[List[TextList], List[TextBlock]]:
        ordered = list_items[0][0] != "\u2022"

        if ordered and len(list_items) == 1:
            elements = []
            for list_item in list_items:
                elements += list_item[1]
            return elements

        textlist = TextList(
            bbox=list_items[0][1][0].bbox, ordered=ordered, items=[])
        for list_item in list_items:
            label_match = self.list_regex.match(
                list_item[1][0].items[0].get_text().strip())
            if not label_match:
                raise RuntimeError(
                    f"Regex failed to refind list label in {list_item[1][0].items[0].get_text().strip()} - this shouldn't be possible!")
            list_item[1][0].items[0].spans[0].text = list_item[1][0].items[0].spans[0].text[label_match.span()[
                1]:].lstrip()
            textlist.append(TextListItem(
                label=list_item[0], items=list_item[1]))

        return [textlist]

    def _find_lists(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        """Identifies lists within a set of ordered layout elements

        Args:
            elements (List[LayoutElement]): Elements, ordered by reading order

        Returns:
            List[LayoutElement]: The same set of elements with any list items removed
                and replaced with lists
        """
        proc_elements: List[LayoutElement] = []

        in_list = False
        list_elements: List[Tuple[str, List[TextBlock]]] = []

        for i, element in enumerate(elements):
            if isinstance(element, TextBlock):
                                
                list_match = self.list_regex.match(element.get_text()[:10].strip())
                
                if element.type not in [TextBlockType.PARAGRAPH, TextBlockType.SMALL, TextBlockType.EMPHASIS]:
                    list_match = False
                    in_list = False

                # Does the box start with something that looks like a list/bullet point
                if not in_list and list_match:
                    in_list = True
                    list_elements = [
                        (self._get_list_index_from_match(list_match), [element])]
                    continue

                # If we're in a list but don't find a bullet/label.
                if in_list and not list_match:

                    # Check to see if we're inline with text but not with the bullet
                    list_line_offset = list_elements[-1][1][-1].items[-1].bbox.x0 - \
                        list_elements[0][1][0].items[0].bbox.x0
                    if list_line_offset > 5 and list_line_offset < 30:
                        if abs(element.bbox.x0 - list_elements[-1][1][-1].items[-1].bbox.x0) < 2:
                            list_elements[-1][1].append(element)
                            continue

                    # Check to see if an ordered list continues in the next element
                    if len(elements) > i+1 and isinstance(elements[i+1], TextBlock):
                        future_e: TextBlock = elements[i+1]  # type:ignore
                        future_match = self.list_regex.match(
                            future_e.get_text())
                        if future_match and list_elements[0][0] != "\u2022" and \
                            self._is_next_list_index(
                                list_elements[-1][0],
                                self._get_list_index_from_match(future_match)
                        ):
                            list_elements[-1][1].append(element)
                            continue

                # Parse block line by line looking for
                if in_list and list_match:
                    next_index = self._get_list_index_from_match(list_match)
                    if self._is_next_list_index(list_elements[-1][0], next_index):
                        list_elements.append((next_index, [element]))
                    else:
                        proc_elements += self._create_list(list_elements)
                        list_elements = [(next_index, [element])]
                    continue

            # Handle any other parts of being a text block
            if len(list_elements) > 0:
                proc_elements += self._create_list(list_elements)
                in_list = False
                list_elements = []

            proc_elements.append(element)
            continue

            if isinstance(element, Aside):
                aside.items = self._find_lists(element.items)

            # If not a list
            proc_elements.append(element)

        if len(list_elements) > 0:
            proc_elements += self._create_list(list_elements)

        return proc_elements

    def _process_page(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        elements = self._find_lists(elements)

        proc_elements = []
        for element in elements:
            if isinstance(element, PageSection):
                proc_elements += element.items
            else:
                proc_elements.append(element)

        return proc_elements

    def _process(self, data: Any) -> Any:

        for page_number, elements in self.get_page_data(data):
            elements = self._process_page(elements)
            data['elements'][page_number] = elements

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):

        colours = {
            TextListItem: "Blue"
        }

        def recursive_add(fig: Figure, element: LayoutElement):
            if isinstance(element, PageSection):
                for i in element.items:
                    recursive_add(fig, i)
            elif isinstance(element, TextListItem):
                point = element.bbox.center()
                point.x -= 40
                add_rect_to_figure(fig, element.bbox, colours[TextListItem])
                add_text_to_figure(
                    fig, point, colours[TextListItem], f"L:{element.label}", 15)
            elif isinstance(element, TextList):
                for i in element.items:
                    recursive_add(fig, i)

        for element in data['elements'][page_number]:
            recursive_add(fig, element)

        fig.add_scatter(x=[None], y=[None], name="List",
                        line={'width': 3, 'color': colours[TextListItem]})
