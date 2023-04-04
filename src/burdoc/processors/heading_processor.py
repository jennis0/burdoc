import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import mode
from plotly.graph_objects import Figure

from ..elements.aside import Aside
from ..elements.bbox import Point
from ..elements.element import LayoutElement
from ..elements.section import PageSection
from ..elements.textblock import TextBlock, TextBlockType
from ..elements.table import Table
from ..utils.render_pages import add_rect_to_figure, add_text_to_figure
from .processor import Processor


class HeadingProcessor(Processor):
    """The HeadingProcessor takes the correctly ordered layout elements and applies additional 
    semantic processing to identify headings and titles. It also generates a hierarchy of 
    headings for the page.

    **Requires:** ['elements']

    **Optional:** None

    **Generators:** ['elements', 'page_hierarchy']
    """

    name: str = "content"

    def __init__(self, log_level: int = logging.INFO):
        self.default_font = ""
        self.default_font_size = 10.

        super().__init__(HeadingProcessor.name, log_level=log_level)

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (['elements'], [])

    def generates(self) -> List[str]:
        return ['elements', 'page_hierarchy']

    def _fit_font_predictor(self, font_statistics):
        counts = {}
        total_lines = 0
        default_font = None
        default_font_count = 0
        max_size = 0

        def str_to_scaled_int(s):
            return int(round(float(s), 1)*10)
        
        for font_family in font_statistics:
            f_counts = font_statistics[font_family]['_counts']
            if len(f_counts) > 0:
                font_max_size = max(f_counts.keys())
                max_size = max(str_to_scaled_int(font_max_size), max_size)
                counts[font_family] = np.zeros(
                    shape=(str_to_scaled_int(font_max_size)+1)
                )
                for size in f_counts:
                    counts[font_family][str_to_scaled_int(size)] += f_counts[size]
                    total_lines += f_counts[size]
                if counts[font_family].sum() > default_font_count:
                    default_font = font_family
                    default_font_count = counts[font_family].sum()

        self.default_font = default_font

        font_count_array = np.zeros(shape=(max_size+1))
        for font_count in counts.values():
            font_count_array[:font_count.shape[0]] += font_count
            
        sorted_indices = list(reversed(font_count_array.argsort(axis=0)))
        self.default_font_size = min(sorted_indices[0]/10., 20.0)

    def _is_heading(self, factors: Dict[str, Any]) -> bool:

        if len(factors['text']) == 0:
            return False
        
        if u"\u2022" in factors['text']:
            return False

        word_count = factors['word_count']
        line_count = factors['line_count']

        if factors['font'] == factors['next_font']:
            word_count += factors['next_len']
            line_count += factors['next_lines']

        if factors['font'] == factors['last_font']:
            word_count += factors['last_len']
            line_count += factors['last_lines']
        
        if factors['size'] < self.default_font_size + 2:
            if factors['word_count'] > 8 or factors['line_count'] > 2:
                return False
            
        if factors['size'] < self.default_font_size + 10:
            if factors['word_count'] > 15 or factors['line_count'] > 3:
                return False

        if factors['word_count'] > 20:
            return False
        
        if factors['all_italics'] and not factors['all_bold'] and \
                (factors['size'] < self.default_font_size + 1 or word_count > 7):
            return False

        para_header = factors['dist_to_last'] > min(5, factors['dist_to_next'] + 1)
        if para_header:
            if factors['all_caps'] and not(factors['next_font'] and factors['next_font'].smallcaps):
                return True

            if factors['all_bold'] and abs(factors['line_align']) > 5 and \
                    abs(factors['dist_to_next']) < 4 and \
                        not(factors['next_font'] and factors['next_font'].bold):
                return True

            if factors['all_bold'] and factors['size'] > self.default_font_size + 0.5:
                return True

            if factors['all_bold'] and factors['dist_to_next'] > 10:
                return True

            if factors['dist_to_next'] < 5 and factors['last_font'] and factors['next_font']:
                if factors['font'].family != factors['last_font'].family and \
                    factors['font'].family != factors['next_font'].family:
                    return True
                
            if factors['dist_to_next'] < 10 and factors['next_font']:
                if factors['font'].size > factors['next_font'].size + 0.5:
                    return True

        if max(factors['sizes']) > self.default_font_size + 2.:
            return True

        matched_colour = factors['next_font'] and \
            factors['font'].colour == factors['next_font'].colour

        if factors['size'] > self.default_font_size + 0.5 and \
            (factors['all_bold'] or factors['all_caps'] or not matched_colour):
            return True

        return False

    def _predict_heading_type(self, factors: Dict[str, Any]):
        size = mode(factors['sizes'], axis=0, keepdims=False)[0]

        if size < self.default_font_size + 0.5:
            return TextBlockType.H6
        for i, t in zip(range(1, 5), [TextBlockType.H5, TextBlockType.H4, TextBlockType.H3, TextBlockType.H2]):
            if size < self.default_font_size*(1.05+0.2*i):
                return t

        return TextBlockType.H1

    def _classify_block(self, element: TextBlock,
                        last_element: Optional[LayoutElement],
                        next_element: Optional[LayoutElement]) -> TextBlockType:

        heading_factors: Dict[str, Any] = {}
        heading_factors['text'] = element.get_text().strip()
        heading_factors['font'] = element.items[0].spans[0].font
        heading_factors['word_count'] = len(element.get_text().split())
        heading_factors['line_count'] = len(element.items)
        heading_factors['all_caps'] = element.get_text().isupper()
        heading_factors['all_bold'] = all(s.font.bold for line in element.items for s in line.spans)
        heading_factors['all_italics'] = all(s.font.italic for line in element.items for s in line.spans)
        heading_factors['dist_to_last'] = element.bbox.y0 - last_element.bbox.y1 if last_element else 5000.
        heading_factors['dist_to_next'] = next_element.bbox.y0 - \
            element.bbox.y1 if next_element and (isinstance(next_element, TextBlock) or isinstance(next_element, Table)) else 5000.
        heading_factors['line_align'] = next_element.bbox.x1 - element.bbox.x1 if next_element else 0.
        heading_factors['sizes'] = [s.font.size for line in element.items for s in line.spans]
        heading_factors['size'] = mode(heading_factors['sizes'], axis=None, keepdims=False)[0]

        if isinstance(next_element, TextBlock):
            heading_factors['next_font'] = next_element.items[0].spans[0].font
            heading_factors['next_len'] = len(next_element.get_text().split())
            heading_factors['next_lines'] = len(next_element.items)
        else:
            heading_factors['next_font'] = None
            heading_factors['next_len'] = 0
            heading_factors['next_lines'] = 0

        if isinstance(last_element, TextBlock):
            heading_factors['last_font'] = last_element.items[-1].spans[0].font
            heading_factors['last_len'] = len(last_element.get_text().split())
            heading_factors['last_lines'] = len(last_element.items)
        else:
            heading_factors['last_font'] = False
            heading_factors['last_len'] = 0
            heading_factors['last_lines'] = 0

        is_heading = self._is_heading(heading_factors)
        if is_heading:
            return self._predict_heading_type(heading_factors)

        size = heading_factors['size']
        if size > self.default_font_size - 1.5:
            if heading_factors['all_italics']:
                return TextBlockType.EMPHASIS
            else:
                return TextBlockType.PARAGRAPH

        return TextBlockType.SMALL

    def _assign_headings(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        proc_elements: List[LayoutElement] = []

        for i, element in enumerate(elements):
            if i > 0:
                last_element = elements[i-1]
            else:
                last_element = None

            if i < len(elements) - 1:
                next_element = elements[i+1]
            else:
                next_element = None

            if isinstance(element, TextBlock):
                element.type = self._classify_block(element, last_element, next_element)
                proc_elements.append(element)
                continue

            if isinstance(element, PageSection):
                if element.default or not (element.backing_drawing or element.backing_image):
                    proc_elements += self._assign_headings(element.items)
                elif len(element.items) > 0:
                    proc_elements.append(
                        Aside(element.bbox, self._assign_headings(element.items))
                    )
                continue

            if isinstance(element, Aside):
                element.items = self._assign_headings(element.items)

            proc_elements.append(element)

        return proc_elements

    def _build_page_hierarchy(self, page_number: int, elements: List[LayoutElement]) -> List[Any]:

        def add_to_hierarchy(textblock: TextBlock, hierarchy: List[Dict[str, Any]],
                             index: int, sub_index: Optional[int] = None):
            if textblock.type in [TextBlockType.PARAGRAPH, TextBlockType.EMPHASIS, TextBlockType.SMALL]:
                return

            size = textblock.items[0].spans[0].font.size
            hierarchy.append(
                {'page': page_number, 'index': [
                    index, sub_index], 'text': textblock.get_text(), 'size': size,
                 'assigned_heading': textblock.type.name.lower()}
            )

        hierarchy: List[Dict[str, Any]] = []
        for i, element in enumerate(elements):

            if isinstance(element, Aside) or isinstance(element, PageSection):
                for j, sub_e in enumerate(element.items):
                    if not isinstance(sub_e, TextBlock):
                        continue
                    add_to_hierarchy(sub_e, hierarchy, i, j)  # type:ignore
                continue

            if not isinstance(element, TextBlock):
                continue

            add_to_hierarchy(element, hierarchy, i)

        return hierarchy

    def _process_page(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        elements = self._assign_headings(elements)
        return elements

    def _process(self, data: Any) -> Any:
        self._fit_font_predictor(data['metadata']['font_statistics'])
        data['page_hierarchy'] = {}
        for page_number, elements in self.get_page_data(data):

            elements = self._process_page(elements)

            data['elements'][page_number] = elements
            data['page_hierarchy'][page_number] = self._build_page_hierarchy(
                page_number, elements)

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):

        colours = {
            PageSection: "Purple",
            TextBlock: "Black",
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
                point = Point(element.bbox.x0+20, element.bbox.y0+10)
                add_rect_to_figure(fig, element.bbox,
                                   colours[element.type.name[0].lower()])
                add_text_to_figure(
                    fig, point, colours[element.type.name[0].lower()], element.type.name, 15)

        for element in data['elements'][page_number]:
            recursive_add(fig, element)
