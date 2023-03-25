import logging
import re
from typing import Any, Dict, List, Optional

from plotly.graph_objects import Figure

from ..elements.bbox import Bbox
from ..elements.element import LayoutElementGroup
from ..elements.layout_objects import DrawingElement, ImageElement, LineElement
from ..elements.section import PageSection
from ..elements.textblock import TextBlock
from .processor import Processor


class LayoutProcessor(Processor):

    def __init__(self, log_level: Optional[int]=logging.INFO):
        super().__init__("layout", log_level=log_level)

        self.block_graph_max_radius = 250
        self.block_vgap_threshold = 2
        self.block_vgap_start = 5
        self.block_halign_threshold = 1
        self.block_size_threshold = 2
        self.section_margin = 5

    def initialise(self):
        return super().initialise()

    def requirements(self) -> List[str]:
        return ["page_bounds", "images", "drawings", "text"]
    
    def generates(self) -> List[str]:
        return ['elements']

    def _create_sections(self, page_bound: Bbox, text : List[LineElement], images : List[ImageElement], drawings : List[DrawingElement]) -> List[PageSection]:
        '''Create sections based on drawn boxes, images, and page dividing lines then assign each text element to a section'''

        page_height = page_bound.height()
        page_width = page_bound.width()

        #Turn line drawings into section breaks
        breaks = [
            d.bbox for d in drawings[DrawingElement.DrawingType.Line]
        ]
        for line in images[ImageElement.ImageType.Line]:
            line.image.save("test.png")
            b = line.bbox
            if b.y0/page_height < 0.95 and b.y0/page_height > 0.05:
                breaks.append(Bbox(max(b.x0,0), b.y0, b.x1, b.y0+1, page_bound.page_width, page_bound.page_height))
                breaks.append(Bbox(max(b.x0,0), b.y1, b.x1, b.y1+1, page_bound.page_width, page_bound.page_height))

        background = None
        if len(images[ImageElement.ImageType.Background]) > 0:
            background = images[ImageElement.ImageType.Background][0]

        #Split the 'default' section into chunks based on large line breaks
        sections = []
        last_y = 0

        for b in breaks:
            if b.width() / page_width > 0.75:
                sections.append(
                        PageSection(
                        items=[],
                        default=True,
                        backing_drawing=None,
                        backing_image=background,
                        bbox = Bbox(page_bound.x0, 
                                    last_y, 
                                    page_bound.x1, 
                                    b.y1, 
                                    page_bound.page_width, 
                                    page_bound.page_height),
                        inline=True
                    )
                )
                last_y = b.y1

        #Turn remaining part of the page into final default section
        sections.append(
            PageSection(
                items=[], 
                default=True, 
                backing_drawing=None, 
                backing_image=background, 
                bbox = Bbox(page_bound.x0, 
                            last_y, 
                            page_bound.x1, 
                            page_bound.y1, 
                            page_bound.page_width, 
                            page_bound.page_height),               
                inline=True
            )   
        )

        #Create sections from each section image
        for i in images[ImageElement.ImageType.Section]:
            sections.append(PageSection(
                    bbox=Bbox(
                        i.bbox.x0+self.section_margin, 
                        i.bbox.y0+self.section_margin, 
                        i.bbox.x1-self.section_margin, 
                        i.bbox.y1-self.section_margin,
                        page_bound.page_width,
                        page_bound.page_height), 
                    items=[], 
                    default=False, 
                    backing_drawing=None, 
                    backing_image=i,
                    inline = i.bbox.width() / page_width > 0.5
                )
            )

        #Create a section from each rectangle
        for d in drawings[DrawingElement.DrawingType.Rect]:
            sections.append(PageSection(
                    bbox=Bbox(
                        d.bbox.x0+self.section_margin,
                        d.bbox.y0+self.section_margin, 
                        d.bbox.x1-self.section_margin, 
                        d.bbox.y1-self.section_margin,
                        page_bound.page_width,
                        page_bound.page_height),  
                    items=[], 
                    default=False, 
                    backing_drawing=d, 
                    backing_image=None,
                    inline = d.bbox.width() / page_width > 0.5
                )
            )

        #Assgn lines to sections
        sections.sort(key=lambda s: s.bbox.y0*1000 + s.bbox.x0)
        if len(sections) > 1:
            for l in text:
                written = False
                if not any(len(sp.text.strip()) > 0 for sp in l.spans):
                    continue
                
                for i,s in enumerate(sections[1:]):
                    if s.bbox.overlap(l.bbox, 'second') > 0.97:
                        s.append(l, update_bbox=False)
                        written = True
                        break
                if not written:
                    sections[0].append(l, update_bbox=False)
        else:
            sections[0].items += text

        #Filter out sections with no lines
        sections = [s for s in sections if len(s.items) > 0 or s.default]

        self.logger.debug(f"Found {len(sections)} section in page")
        for i,s in enumerate(sections):
            self.logger.debug(f"Section {i+1} - {s.bbox} - {len(s.items)} items")

        return sections

    def _create_blocks(self, section: PageSection) -> List[TextBlock]:
        '''Group all of the items within a section into blocks'''
        blocks = []
        section.items.sort(key=lambda l: l.bbox.y0*1000 + l.bbox.x0)
        list_re = re.compile(u"^(\u2022)|^\((\d+)\.?\)|^(\d+)\.\s|^([a-z])\.\s|^\(([a-z])\)\.?", re.UNICODE)


        for line in section.items:
            self.logger.debug(f"line: {line.get_text()}")
            self.logger.debug(line)


            used = False
            line_font = None

            for s in line.spans:
                if len(s.text.strip()) > 0:
                    line_font = s.font
                    break

            superscript = len(line.get_text()) < 3 and line.spans[0].font.size < 7

            for block in blocks:
                if used:
                    break

                last_real_item = block.items[-1]
                for i in range(len(block.items)):
                    l = block.items[-i]
                    if len(l.get_text()) < 3 and l.spans[0].font.size < 7:
                        continue
                    last_real_item = l
                    break

                if not block.open:
                    continue

                self.logger.debug(f"block: {block.get_text()}")
                self.logger.debug(block.items[-1])

                for i in range(len(block.items[-1].spans)):
                    if last_real_item.spans[-(i+1)].text.strip() != "":
                        block_font = last_real_item.spans[-(i+1)].font
                        break

                ### Only allow merging with the block if it is of comparable width and
                ### within the same distance as previous lines in this block

                is_bullet = list_re.match(line.spans[0].text.lstrip()) is not None
                line_overlap_with_block = line.bbox.x_overlap(block.bbox, 'first')
                linegap = line.bbox.y0 - block.bbox.y1
                block_overlap_with_line = line.bbox.x_overlap(block.bbox, 'second')
                total_overlap = line.bbox.overlap(block.bbox, 'first')

                if line_font and block_font and not superscript:
                    matched_font = abs(line_font.size - block_font.size) < 0.1 and \
                        line_font.family == block_font.family
                    matched_bold = (line_font.bold == block_font.bold) and (line_font.italic == block_font.italic)
                    fuzzy_line_continuation = len(block.items) < 2 or ((abs(last_real_item.bbox.x1 - block.bbox.x1) < 20) and (line.bbox.x0 - last_real_item.bbox.x0) < 2)
                    if linegap < 5:
                        matched_font = matched_font and (fuzzy_line_continuation or matched_bold)
                    else:
                        matched_font = matched_font and matched_bold
                else:
                    matched_font = True

                block_linegap = 8 if len(block.items) == 1 else max(block.items[1].bbox.y0 - block.items[0].bbox.y1 + 1, 3)

                self.logger.debug(f"linegap={linegap}, matched_font={matched_font}, line_overlap={line_overlap_with_block},"+\
                                   f"block_overlap={block_overlap_with_line}, is_bullet={is_bullet}")


                if line_overlap_with_block > 0.08:
                    if linegap < block_linegap and matched_font and not is_bullet:
                        block.append(line)
                        self.logger.debug("Appending line to block")
                        used = True
                        continue

                    if total_overlap> 0.9:
                        block.append(line)
                        self.logger.debug("Appending line to block due to bbox overlap")
                        used = True
                        continue

                    if linegap < block_linegap and len(line.get_text().strip()) == 1 and line.spans[0].font.size < 12:
                        block.append(line)
                        self.logger.debug("Appening line to block as it's single character")
                        used = True

                    if not matched_font or is_bullet:
                        block.open = False
                        self.logger.debug("Closing block")
                        continue

                    block.open = False
                    self.logger.debug("Closing block")
                    continue

            if not used:
                blocks.append(TextBlock(items=[line], open=True))
                
        used = [False for _ in blocks]
        for i,b in enumerate(blocks):
            if used[i]:
                continue
            for j,b2 in enumerate(blocks[i+1:]):
                if used[i+j+1]:
                    continue
                if b2.bbox.overlap(b.bbox, 'first') > 0.5:
                    b.items += b2.items
                    b.items.sort(key=lambda l: l.bbox.y0*5 + l.bbox.x0)
                    used[i+j+1] = True

        blocks = [b for i,b in enumerate(blocks) if not used[i]] 

        split_blocks = []
        for b in blocks:
            new_blocks = []
            line_start = b.items[0].bbox.x0
            last_line = 0
            skip_next_i = 0
            for i,l in enumerate(b.items[1:-1]):
                if skip_next_i > 0:
                    skip_next_i -= 1
                    continue

                compare_to = i+2
                finish=False
                while b.items[compare_to].bbox.y1 < (l.bbox.y1 + 3) or len(b.items[compare_to].get_text()) < 3:
                    compare_to += 1
                    skip_next_i += 1

                    if compare_to == len(b.items):
                        finish=True
                        break
                if finish:
                    break

                if (l.bbox.x0 - line_start) > 1 and (b.items[compare_to].bbox.x0 - line_start) < 1:
                    new_blocks.append(
                        TextBlock(items=b.items[last_line:i+1])
                    )
                    last_line = i+1
                    line_start = b.items[compare_to].bbox.x0
                else:
                    line_start = l.bbox.x0

            if last_line > 0  and last_line != len(b.items) - 1:
                new_blocks.append(
                    TextBlock(items=b.items[last_line:])
                )
            elif last_line == 0:
                new_blocks.append(b)
            split_blocks += new_blocks
                    
        self.logger.debug(f"Found {len(split_blocks)} blocks in section.")            
        return split_blocks
            
    def process(self, data: Any) -> Any:
        data['elements'] = {}
        for pn, page_bound, images, drawings, elements in self.get_page_data(data):

            #self.logger.debug(f"Computing layout for page {pn}")
            sections = self._create_sections(page_bound, elements, images, drawings)
        
            for s in sections:
                s.items = self._create_blocks(s)

            data['elements'][pn] = sections

        #self.logger.debug("Finished computing layout")

    def add_generated_items_to_fig(self, page_number:int, fig: Figure, data: Dict[str, Any]):

        colours = {
            PageSection:"Purple",
            TextBlock:"Black"
        }

        def add_rect(fig, bbox, colour):
            fig.add_shape(
                type='rect', xref='x', yref='y', opacity=0.6,
                x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
                line=dict(color=colour, width=3)
            )

        def recursive_add(fig, e):
            if isinstance(e, PageSection):
                add_rect(fig, e.bbox, colours[PageSection])
                for i in e.items:
                    recursive_add(fig, i)
            elif isinstance(e, TextBlock):
                add_rect(fig, e.bbox, colours[TextBlock])
            elif isinstance(e, LayoutElementGroup) or isinstance(e, list):
                for i in e:
                    recursive_add(fig, i)

        for e in data['elements'][page_number]:
            recursive_add(fig, e)

        fig.add_scatter(x=[None], y=[None], name="Section", line=dict(width=3, color=colours[PageSection]))
        fig.add_scatter(x=[None], y=[None], name="Block", line=dict(width=3, color=colours[TextBlock]))