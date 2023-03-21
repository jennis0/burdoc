from logging import Logger
from typing import Dict, List, Any, Tuple
import re
from plotly.graph_objects import Figure
import numpy as np

from ..elements.element import LayoutElement
from .processor import Processor

from ..elements.textblock import TextBlock, TextBlockType
from ..elements.section import PageSection
from ..elements.content_objects import TextList, TextListItem, Aside

import plotly.express as plt


class ContentProcessor(Processor):

    def __init__(self, logger: Logger):
        self.para_size = {}
        super().__init__("Content", logger)

    def initialise(self):
        return super().initialise()

    def requirements(self) -> List[str]:
        return ['elements']
    
    def generates(self) -> List[str]:
        return ['elements', 'page_hierarchy']
    
    def _get_list_index_from_match(self, match: re.Match) -> str:
        for g in match.groups():
            if g:
                return g

    def _is_next_list_index(self, last_index: str, next_index: str) -> bool:
        if last_index == u"\u2022":
            if next_index == u"\u2022":
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
        for font_family in counts:
            #print(font_family, counts.keys())
            if counts[font_family].sum() / total_lines > 0.2:
                para_size = int(counts[font_family].argmax()) + 1
                self.para_size[font_family] = [
                    (para_size - 2, TextBlockType.Small),
                    (para_size + 1, TextBlockType.Paragraph),
                    (para_size + 3, TextBlockType.H3),
                    (para_size + 5, TextBlockType.H2)
                ]
        
        for font_family in counts:
            if font_family not in self.para_size:
                self.para_size[font_family] = self.para_size[default_font]
        self.para_size['default'] = self.para_size[default_font]

            
            # fig = plt.bar(x=np.arange(0, counts[font_family].shape[0]), y=counts[font_family])
            # fig.add_annotation(x=10, y=10, showarrow=False, text=font_family)
            # fig.show()      

    def _get_text_class(self, block: TextBlock):
        fs = block.items[-1].spans[-1].font.size
        fam = block.items[-1].spans[-1].font.family

        if len(block.items) > 3:
            return TextBlockType.Paragraph

        type = TextBlockType.H1
        if fam not in self.para_size:
            fam = 'default'
        for v,t in self.para_size[fam]:
            if fs < v:
                type = t
                break
    
        if type == TextBlockType.Paragraph:
            all_italic=True
            for i in block.items:
                if not all(s.font.italic for s in i.spans):
                    all_italic = False
                    break
            if all_italic:
                return TextBlockType.Emphasis
            
        return t


    def _create_list(self, list_items: List[Tuple[str, List[TextBlock]]]) -> TextList:
        ordered = list_items[0] != u"\u2022"
        list = TextList(bbox=list_items[0][1][0].bbox, ordered=ordered, items=[])
        for li in list_items:
            list.append(TextListItem(label=li[0], items=li[1]))
        
        return list            

    def _process_text_block(self, block: TextBlock) -> List[LayoutElement]:
        block.variant = self._get_text_class(block)
        return [block]

    def _preprocess(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        proc_elements = []

        in_list = False
        list_elements = []

        list_re = re.compile(u"^(\u2022)|^\((\d+)\.?\)|^(\d+)\.\s|^([a-z])\.\s|^\(([a-z])\)\.?", re.UNICODE)

        for i,e in enumerate(elements):
            if isinstance(e, TextBlock):
                list_match = list_re.match(e.get_text()[:10].strip())

                ### Does the box start with something that looks like a list/bullet point
                if not in_list and list_match:
                    in_list = True
                    list_elements = [(self._get_list_index_from_match(list_match), [e])]
                    continue

                if in_list and list_match:
                    list_elements.append((self._get_list_index_from_match(list_match), [e]))
                    continue

                ### If we're processing a list, do we think we're still in it?
                if in_list and not list_match:
                    if e.items[0].bbox.x0 - list_elements[-1][1][-1].bbox.x0 > 1:
                        in_list = False
                    if len(elements) > i+1 and isinstance(elements[i+1], TextBlock):
                        if list_re.match(elements[i+1].get_text()) is not None:
                            in_list = True
                        else:
                            in_list = False

                if not in_list and len(list_elements) > 0:
                    proc_elements.append(self._create_list(list_elements))
                    list_elements = []


                ### Parse block line by line looking for 
                if in_list and list_match:
                    next_index = self._get_list_index_from_match(list_match)
                    if self._is_next_list_index(list_elements[-1][0], next_index):
                        list_elements.append((next_index, [e]))
                        continue
                    else:
                        proc_elements.append(self._create_list(list_elements))
                        list_elements = []

                #Handle any other parts of being a text block
                proc_elements += self._process_text_block(e)
                continue

            if isinstance(e, PageSection):
                if e.default or not (e.backing_drawing or e.backing_image):
                    proc_elements += self._preprocess(e.items)
                    continue
                else:
                    proc_elements.append(Aside(e.bbox, self._preprocess(e.items), False))
                    continue

            ###If not a list
            proc_elements.append(e)

        if len(list_elements) > 0:
            proc_elements.append(self._create_list(list_elements))

        return proc_elements

            
    def _build_page_hierarchy(self, page_number: int, elements: List[LayoutElement]) -> List[Any]:

        def add_to_hierarchy(e: LayoutElement, hierarchy: List[LayoutElement], index: int, sub_index: int):
            if e.variant in [TextBlockType.Paragraph, TextBlockType.Emphasis, TextBlockType.Small]:
                return

            size = e.items[0].spans[0].font.size
            hierarchy.append(
                    {'page':page_number, 'index':[index, sub_index], 'text':e.get_text(), 'size': size}
                )

        hierarchy = []
        for i,e in enumerate(elements):

            if isinstance(e, Aside):
                for j,sub_e in enumerate(e.items):
                    if not isinstance(e, TextBlock):
                        continue
                    add_to_hierarchy(sub_e, hierarchy, i, j)
                continue

            if not isinstance(e, TextBlock):
                continue

            add_to_hierarchy(e, hierarchy, i, None)

        return hierarchy


    def _process_page(self, elements: List[LayoutElement]) -> Dict[str, List[Any]]:
        elements = self._preprocess(elements)

        proc_elements = []
        for e in elements:
            if isinstance(e, PageSection):
                proc_elements += e.items
            else:
                proc_elements.append(e)

        return proc_elements


    def process(self, data: Any) -> Any:
        self._fit_font_predictor(data['metadata']['font_statistics'])
        data['page_hierarchy'] = {}
        for page_number, elements in self.get_page_data(data):
            elements = self._process_page(elements)
            data['elements'][page_number] = elements
            data['page_hierarchy'][page_number] = self._build_page_hierarchy(page_number, elements)


    def add_generated_items_to_fig(self, page_number:int, fig: Figure, data: Dict[str, Any]):

        colours = {
            PageSection:"Green",
            TextBlock:"Black",
            TextListItem:"Blue",
            'a': "pink",
            "p": "black",
            "h": "green",
            's': 'grey',
            'e': 'darkgrey'
        }

        def add_rect(fig, bbox, colour, text=None, add_shape=True, side="left"):
            if add_shape:
                fig.add_shape(
                    type='rect', xref='x', yref='y', opacity=0.6,
                    x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
                    line=dict(color=colour, width=3)
                )
            if text is not None:
                fig.add_annotation(dict(font=dict(color=colour,size=15),
                                        x=bbox.x0 - 20 if side == "left" else bbox.x1 - 10,
                                        y=bbox.y0,
                                        showarrow=False,
                                        font_family="Arial Black",
                                        text=text))

        def recursive_add(fig, e):
            if isinstance(e, PageSection):
                for i in e.items:
                    recursive_add(fig, i)
            elif isinstance(e, TextBlock):
                add_rect(fig, e.bbox, colours[e.variant.name[0].lower()], add_shape=False, text=e.variant.name, side="right")
            elif isinstance(e, TextListItem):
                add_rect(fig, e.bbox, colours[TextListItem], f"L:{e.label}")
            elif isinstance(e, TextList):
                for i in e.items:
                    recursive_add(fig, i)
            

        for e in data['elements'][page_number]:
            recursive_add(fig, e)

        fig.add_scatter(x=[None], y=[None], name="List", line=dict(width=3, color=colours[TextListItem]))
