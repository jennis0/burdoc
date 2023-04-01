import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from plotly.graph_objects import Figure

from ..elements.aside import Aside
from ..elements.bbox import Point
from ..elements.element import LayoutElement
from ..elements.section import PageSection
from ..elements.textblock import TextBlock, TextBlockType
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
        self.para_size: Dict[str, List[Tuple[float, TextBlockType]]] = {}

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

        for font_family in font_statistics:
            f_counts = font_statistics[font_family]['_counts']
            if len(f_counts) > 0:
                counts[font_family] = np.zeros(
                    shape=(int(max(f_counts.keys())+1)))
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
        font_size = block.items[0].spans[-1].font.size
        font_fam = block.items[0].spans[-1].font.family

        if len(block.items) > 3:
            return TextBlockType.PARAGRAPH

        subtype = TextBlockType.H1
        if font_fam not in self.para_size:
            font_fam = 'default'
        for max_font_size, textblock_type in self.para_size[font_fam]:
            if font_size < max_font_size:
                subtype = textblock_type
                break

        if subtype == TextBlockType.PARAGRAPH:
            all_italic = True
            for i in block.items:
                if not all(s.font.italic for s in i.spans):
                    all_italic = False
                    break
            if all_italic:
                return TextBlockType.EMPHASIS

        return subtype

    def _process_text_block(self, block: TextBlock) -> TextBlock:
        block.type = self._get_text_class(block)
        return block

    def _assign_headings(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        proc_elements: List[LayoutElement] = []

        for element in elements:
            if isinstance(element, TextBlock):
                element.type = self._get_text_class(element)
                proc_elements.append(element)
                continue

            if isinstance(element, PageSection):
                print(element)
                if element.default or not (element.backing_drawing or element.backing_image):
                    proc_elements += self._assign_headings(element.items)
                else:
                    proc_elements.append(
                        Aside(element.bbox, self._assign_headings(element.items))
                    )
                continue
                    
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
                 'assigned_heading':textblock.type.name.lower()}
            )

        hierarchy: List[Dict[str, Any]] = []
        for i, element in enumerate(elements):

            if isinstance(element, Aside):
                for j, sub_e in enumerate(element.items):
                    if not isinstance(element, TextBlock):
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
