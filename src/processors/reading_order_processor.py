from typing import Any, List, Dict
import logging

from plotly.graph_objects import Figure

from ..elements.bbox import Bbox
from ..elements.layout_objects import ImageElement
from ..elements.section import PageSection
from ..elements.element import LayoutElement, LayoutElementGroup
from ..elements.table import Table
from ..elements.textblock import TextBlock
from ..elements.content_objects import Column

from .processor import Processor

class ReadingOrderProcessor(Processor):

    def __init__(self, logger: logging.Logger):
        super().__init__("ReadingOrder", logger)

        self.block_graph_max_radius = 250
        self.block_vgap_threshold = 2
        self.block_vgap_start = 5
        self.block_halign_threshold = 1
        self.block_size_threshold = 2
        self.section_margin = 5

    @staticmethod
    def requirements() -> List[str]:
        return ["page_bounds", "elements", "images", "tables"]
    
    @staticmethod
    def generates() -> List[str]:
        return ['elements']
            
    def _flow_items(self, page_bound: Bbox, elements: List[LayoutElement]):
        
        elements.sort(key=lambda e: e.bbox.y0*100 + e.bbox.x0)
        page_width = page_bound.width()
        center = page_bound.center()

        columns = []
        for e in elements:
            used = False
            self.logger.debug(e)
            for c in columns:
                if not c.open:
                    continue

                c_full_page = c.bbox.width() / page_width > 0.6
                e_full_page = e.bbox.width() / page_width > 0.6
                l_aligned = abs(c.bbox.x0 - e.bbox.x0) < 2
                c_centered = abs(c.bbox.center().x - center.x) < 10
                e_centered = abs(e.bbox.center().x - center.x) < 10

                dy = e.bbox.y0 - c.bbox.y1
                dx_col= c.bbox.x_overlap(e.bbox, 'first')
                dx_block = c.bbox.x_overlap(e.bbox, 'second')
                append = False

                self.logger.debug(f"dy: {dy}, col: {dx_col}, block: {dx_block}, col_full_page: {c_full_page}, el_full_page: {e_full_page}, col_centered: {c_centered}, el_centered: {e_centered}")

                stop = False
                #If element starts above column end and the majority of the element overlaps
                #with it then merge
                if dy < 0:
                    if dx_block > 0.8:
                        append = True

                #Break between column/full page elements
                if not l_aligned and (\
                    (c_full_page and not e_full_page) or \
                    (e_full_page and not c_full_page)):
                    stop = True

                #Break between centered and non centered elements
                if not l_aligned and (\
                    (c_centered and not e_centered) \
                        or (e_centered and not c_centered)
                ):
                    stop = True

                #Merge if it's within ~2 lines and aligned
                #Don't merge if column starts to the right of the element center
                if not stop and not append and c.bbox.x0 < e.bbox.center().x:
                    if abs(dy) < 30:
                        if dx_col > (0.1 if not c_full_page else 0.5) :
                            append = True
                    elif abs(dy) < 30:
                        if dx_col > 0.6:
                            append = True
                
                if append:
                    c.append(e)
                    used = True
                    self.logger.debug("Appended")
                    break
                elif dx_col > 0.1:
                    c.open = False
                    self.logger.debug("Closing column")


            if not used:
                columns.append(
                    LayoutElementGroup(items=[e], open=True)
                )
                self.logger.debug("Creating new column")

        #Merge overlapping columns
        remove_cols = set()
        for i in range(0, len(columns)):
            if i in remove_cols:
                continue
            for j in range(0, len(columns)):
                if i == j or j in remove_cols:
                    continue
                if columns[i].bbox.overlap(columns[j].bbox, 'min') > 0.5:
                    columns[i].merge(columns[j])
                    remove_cols.add(j)
        columns = [c for i,c in enumerate(columns) if i not in remove_cols]
        self.logger.debug(f"Removing columns {remove_cols}")

        columns.sort(key=lambda c: round(c.bbox.y0/10)*1000 + c.bbox.x0)
        self.logger.debug(f"Found {len(columns)} columns")

        return columns
                    

    def _flow_columns(self, page_bound: Bbox, columns: List[LayoutElement]) -> List[LayoutElement]:
        page_width = page_bound.width()
        sections = []
        current_section = []
        is_full = None
        for c in columns:
            c_is_full = c.bbox.width() / page_width > 0.5
            if is_full is not None and c_is_full != is_full:
                sections.append(current_section)
                current_section = [c]
            else:
                current_section.append(c)
            is_full = c_is_full
        if len(current_section) > 0:
            sections.append(current_section)

        sorted = []            
        for s in sections:
            s.sort(key=lambda c: round(c.bbox.y0/5, 0) * 100 + c.bbox.x0)
            sorted += s
        return sorted

    def _flow_content(self, page_bound: Bbox, sections: List[PageSection], images: List[ImageElement]):
        default_sections = [s for s in sections if s.default]
        other_sections = [s for s in sections if not s.default]

        used_images = set()

        for section in other_sections:
            
            inline_images = []
            outline_images = []
            for i,im in enumerate(images):
                if i in used_images:
                    continue
                if im.bbox.overlap(section.bbox, 'first') > 0.9:
                    overlap = 0
                    for block in section.items:
                        overlap += im.bbox.overlap(block.bbox, 'first')
                    if overlap > 0.2:
                        outline_images.append(PageSection(im.bbox, [im]))
                    else:
                        inline_images.append(im)
                    used_images.add(i)
                        
            columns = self._flow_items(page_bound, section.items + inline_images)
            columns = self._flow_columns(page_bound, columns + outline_images)

            for d in default_sections:
                if section.bbox.overlap(d.bbox, 'first'):
                    d.items.append(section)

        complete_sections = []
        for section in default_sections:

            inline_images = []
            outline_images = []
            for i,im in enumerate(images):
                if i in used_images:
                    continue

                if im.bbox.overlap(section.bbox, 'first') > 0.9:

                    if isinstance(im, ImageElement) and im.bbox.width(norm=True) > 0.6 or im.bbox.height(norm=True) > 0.6:
                        outline_images.append(PageSection(im.bbox, [im]))
                        used_images.add(i)
                        continue

                    overlap = 0
                    for block in section.items:
                        overlap += im.bbox.overlap(block.bbox, 'first')
                    if overlap > 0.2:
                        outline_images.append(PageSection(im.bbox, [im]))
                    else:
                        inline_images.append(im)
                    used_images.add(i)

            columns = self._flow_items(page_bound, section.items + inline_images)
            columns = self._flow_columns(page_bound, columns + outline_images)
            complete_sections.append(columns)

        #Merge images with sections
        for i,im in enumerate(images):
            if i not in used_images:
                complete_sections.append([PageSection(im.bbox, [im])])

        return complete_sections

    def process(self, data: Any) -> Any:
        for pn, page_bound, elements, images, tables in self.get_page_data(data):
            data['elements'][pn] = self._flow_content(page_bound, elements, images[ImageElement.ImageType.Primary] + tables)

        self.logger.debug("Finished computing layout")

    @staticmethod
    def add_generated_items_to_fig(page_number:int, fig: Figure, data: Dict[str, Any]):

        colours = {
            "PageSection":"Green",
            "TextBlock":"Black",
            "Table":"Aqua",
            "ImageElement":"Red",
        }

        def add_rect(fig, bbox, colour, order=None):
            fig.add_shape(
                type='rect', xref='x', yref='y', opacity=0.6,
                x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
                line=dict(color=colour, width=3)
            )
            if order is not None:
                fig.add_annotation(dict(font=dict(color='DarkOrange',size=20),
                                        x=bbox.center().x,
                                        y=bbox.center().y,
                                        showarrow=False,
                                        font_family="Arial Black",
                                        text=order))

        item_order = 1

        def recursive_add(colours, fig, e, item_order):
            if isinstance(e, PageSection):
                add_rect(fig, e.bbox, colours["PageSection"])
                for i in e:
                    item_order = recursive_add(colours, fig, i, item_order)
            elif type(e).__name__ in colours:
                add_rect(fig, e.bbox, colours[type(e).__name__], item_order)
                item_order += 1
            elif isinstance(e, LayoutElementGroup):
                add_rect(fig, e.bbox, colours['PageSection'])
                for item in e:
                    item_order = recursive_add(colours, fig, item, item_order)
            elif isinstance(e, list) or isinstance(e, LayoutElementGroup):
                for item in e:
                    item_order = recursive_add(colours, fig, item, item_order)

            return item_order

        for e in data['elements'][page_number]:
            item_order = recursive_add(colours, fig, e, item_order)

        fig.add_scatter(x=[None], y=[None], name="Section", line=dict(width=3, color=colours["PageSection"]))
        fig.add_scatter(x=[None], y=[None], name="TextBlock", line=dict(width=3, color=colours["TextBlock"]))
        fig.add_scatter(x=[None], y=[None], name="Table", line=dict(width=3, color=colours["Table"]))
        fig.add_scatter(x=[None], y=[None], name="Image", line=dict(width=3, color=colours["ImageElement"]))