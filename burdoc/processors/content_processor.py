import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from plotly.graph_objects import Figure

from ..elements.aside import Aside
from ..elements.element import LayoutElement
from ..elements.section import PageSection
from ..elements.textblock import TextBlock, TextBlockType
from ..elements.textlist import TextList, TextListItem
from .processor import Processor

from ..utils.render_pages import add_rect_to_figure, add_text_to_figure


class ContentProcessor(Processor):
    """The ContentProcessor takes the correctly ordered layout elements and applies additional 
    semantic processing. It generates lists, applies a basic text type classifier to find 
    headings, and generates a hierarchy of headings for the page.
    
    Requires: ['elements']
    Optional: None
    Generators: ['elements', 'page_hierarchy']
    """
    
    name: str = "content"

    def __init__(self, log_level: int=logging.INFO):
        self.para_size: Dict[str, List[Tuple[float, TextBlockType]]] = {}
        self.list_regex = re.compile(
            "(?:(\u2022)|\(?([a-z])\)\.?|\(?([0-9]+)\)\.?|([0-9]+)\.)(?:\s|$)", #pylint: disable=W1401
            re.UNICODE
        ) 


        super().__init__(ContentProcessor.name, log_level=log_level)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (['elements'], [])
   
    def generates(self) -> List[str]:
        return ['elements', 'page_hierarchy']
   
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
            if int(next_index) - int(last_index) == 1:
                return True
        else:
            if ord(next_index) - ord(last_index) == 1:
                return True

        return False

    def _fit_font_predictor(self, font_statistics):
        counts = {}
        total_lines = 0
        default_font = None
        default_font_count = 0
        
        for font_family in font_statistics:
            f_counts = font_statistics[font_family]['_counts']
            if len(f_counts) > 0:
                counts[font_family] = np.zeros(shape=(int(max(f_counts.keys())+1)))
                for size in f_counts:
                    counts[font_family][int(size)] += f_counts[size]
                    total_lines += f_counts[size]
                if counts[font_family].sum() > default_font_count:
                    default_font = font_family
                    default_font_count = counts[font_family].sum()

        self.para_size = {}
        for font_family, family_count in counts.items():
            if family_count.sum() / total_lines > 0.2:
                para_size = int(family_count.argmax()) + 1
                self.para_size[font_family] = [
                    (para_size - 2, TextBlockType.SMALL),
                    (para_size + 0.5, TextBlockType.PARAGRAPH),
                    (para_size + 2, TextBlockType.H5),
                    (para_size + 4, TextBlockType.H4),
                    (para_size + 6, TextBlockType.H3),
                    (para_size + 10, TextBlockType.H2)
                ]

        for font_family in counts:
            if font_family not in self.para_size:
                self.para_size[font_family] = self.para_size[default_font]

        if default_font:
            self.para_size['default'] = self.para_size[default_font]

    def _get_text_class(self, block: TextBlock):
        fs = block.items[0].spans[-1].font.size
        fam = block.items[0].spans[-1].font.family

        if len(block.items) > 3:
            return TextBlockType.PARAGRAPH

        variant = TextBlockType.H1
        if fam not in self.para_size:
            fam = 'default'
        for v,t in self.para_size[fam]:
            if fs < v:
                variant = t
                break

        if variant == TextBlockType.PARAGRAPH:
            all_italic=True
            for i in block.items:
                if not all(s.font.italic for s in i.spans):
                    all_italic = False
                    break
            if all_italic:
                return TextBlockType.EMPHASIS

        return variant


    def _create_list(self, list_items: List[Tuple[str, List[TextBlock]]]) -> Union[List[TextList], List[TextBlock]]:
        ordered = list_items[0][0] != "\u2022"

        if ordered and len(list_items) == 1:
            elements = []
            for list_item in list_items:
                elements += list_item[1]
            return elements
        
        textlist = TextList(bbox=list_items[0][1][0].bbox, ordered=ordered, items=[])
        for list_item in list_items:
            label_match = self.list_regex.match(list_item[1][0].items[0].get_text())
            if not label_match:
                raise RuntimeError("Regex failed to refind list label - this shouldn't be possible!")
            list_item[1][0].items[0].spans[0].text = list_item[1][0].items[0].spans[0].text[label_match.span()[1]:].lstrip()
            textlist.append(TextListItem(label=list_item[0], items=list_item[1]))
        
        return [textlist]

    def _process_text_block(self, block: TextBlock) -> TextBlock:
        block.type = self._get_text_class(block)
        return block

    def _preprocess(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        proc_elements: List[LayoutElement] = []

        in_list = False
        list_elements: List[Tuple[str, List[TextBlock]]] = []

        for i,e in enumerate(elements):
            if isinstance(e, TextBlock):
                list_match = self.list_regex.match(e.get_text()[:10].strip())
                processed_tb = self._process_text_block(e)

                ### Does the box start with something that looks like a list/bullet point
                if not in_list and list_match:
                    in_list = True
                    list_elements = [(self._get_list_index_from_match(list_match), [e])]
                    continue
                
                ### If we're in a list but don't find a bullet/label. 
                if in_list and not list_match:

                    # Check to see if we're inline with text but not with the bullet
                    list_line_offset = list_elements[-1][1][-1].items[-1].bbox.x0 - \
                        list_elements[0][1][0].items[0].bbox.x0
                    if  list_line_offset < 30 and list_line_offset > 5:
                        if abs(e.bbox.x0 - list_elements[-1][1][-1].items[-1].bbox.x0) < 2:
                            list_elements[-1][1].append(e)
                            continue
                        
                    # Check to see if an ordered list continues in the next element
                    if len(elements) > i+1 and isinstance(elements[i+1], TextBlock):
                        future_e: TextBlock = elements[i+1] #type:ignore
                        future_match = self.list_regex.match(future_e.get_text())
                        if future_match and list_elements[0][0] != "\u2022" and \
                            self._is_next_list_index(
                                list_elements[-1][0], 
                                self._get_list_index_from_match(future_match)
                            ):
                            list_elements[-1][1].append(e)
                            continue

                ### Parse block line by line looking for 
                if in_list and list_match:
                    next_index = self._get_list_index_from_match(list_match)
                    if self._is_next_list_index(list_elements[-1][0], next_index):
                        list_elements.append((next_index, [e]))
                    else:
                        proc_elements += self._create_list(list_elements)
                        list_elements = [(next_index, [e])]
                    continue

                #Handle any other parts of being a text block     
                if len(list_elements) > 0:
                    proc_elements += self._create_list(list_elements)
                    in_list = False
                    list_elements = []

                proc_elements.append(processed_tb)
                continue

            if isinstance(e, PageSection):
                if e.default or not (e.backing_drawing or e.backing_image):
                    proc_elements += self._preprocess(e.items)
                    continue
                else:
                    proc_elements.append(Aside(e.bbox, self._preprocess(e.items)))
                    continue

            ###If not a list
            proc_elements.append(e)

        if len(list_elements) > 0:
            proc_elements += self._create_list(list_elements)

        return proc_elements

            
    def _build_page_hierarchy(self, page_number: int, elements: List[LayoutElement]) -> List[Any]:

        def add_to_hierarchy(textblock: TextBlock, hierarchy: List[Dict[str, Any]], index: int, sub_index: Optional[int]=None):
            if textblock.type in [TextBlockType.PARAGRAPH, TextBlockType.EMPHASIS, TextBlockType.SMALL]:
                return

            size = textblock.items[0].spans[0].font.size
            hierarchy.append(
                    {'page':page_number, 'index':[index, sub_index], 'text':textblock.get_text(), 'size': size}
                )

        hierarchy: List[Dict[str, Any]] = []
        for i,e in enumerate(elements):

            if isinstance(e, PageSection):
                for j,sub_e in enumerate(e.items):
                    if not isinstance(e, TextBlock):
                        continue
                    add_to_hierarchy(sub_e, hierarchy, i, j) #type:ignore
                continue

            if not isinstance(e, TextBlock):
                continue

            add_to_hierarchy(e, hierarchy, i)

        return hierarchy


    def _process_page(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        elements = self._preprocess(elements)

        proc_elements = []
        for element in elements:
            if isinstance(element, PageSection):
                proc_elements += element.items
            else:
                proc_elements.append(element)

        return proc_elements


    def _process(self, data: Any) -> Any:
        self._fit_font_predictor(data['metadata']['font_statistics'])
        data['page_hierarchy'] = {}
        for page_number, elements in self.get_page_data(data):
            elements = self._process_page(elements)
            data['elements'][page_number] = elements
            data['page_hierarchy'][page_number] = self._build_page_hierarchy(page_number, elements)


    def add_generated_items_to_fig(self, page_number:int, fig: Figure, data: Dict[str, Any]):

        colours = {
            PageSection:"Purple",
            TextBlock:"Black",
            TextListItem:"Blue",
            'a': "pink",
            "p": "black",
            "h": "green",
            's': 'grey',
            'e': 'darkgrey'
        }

        def recursive_add(fig: Figure, element: LayoutElement):
            if isinstance(element, PageSection):
                for i in element.items:
                    recursive_add(fig, i)
            elif isinstance(element, TextBlock):
                point = element.bbox.center()
                point.x -= 15
                add_rect_to_figure(fig, element.bbox, colours[element.type.name[0].lower()])
                add_text_to_figure(fig, point, colours[element.type.name[0].lower()], element.type.name)
            elif isinstance(element, TextListItem):
                point = element.bbox.center()
                point.x -= 15
                add_rect_to_figure(fig, element.bbox, colours[TextListItem])
                add_text_to_figure(fig, point, colours[TextListItem], f"L:{element.label}")
            elif isinstance(element, TextList):
                for i in element.items:
                    recursive_add(fig, i)
            

        for element in data['elements'][page_number]:
            recursive_add(fig, element)

        fig.add_scatter(x=[None], y=[None], name="List", line=dict(width=3, color=colours[TextListItem]))
