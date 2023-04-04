import logging
from typing import Any, Dict, List, Tuple

from plotly.graph_objects import Figure

from ..elements.bbox import Bbox
from ..elements.drawing import DrawingElement, DrawingType
from ..elements.element import LayoutElementGroup
from ..elements.image import ImageElement, ImageType
from ..elements.line import LineElement
from ..elements.section import PageSection
from ..elements.textblock import TextBlock
from ..utils.render_pages import add_rect_to_figure
from ..utils.regexes import get_list_regex
from .processor import Processor


class LayoutProcessor(Processor):
    """The LayoutProcessor handles dividing the page into sections, assigning text within each section 
    and 'blocking' lines into paragraphs.

    Requires: ['page_bounds', 'image_elements', 'drawing_elements', 'text_elements']
    Optional: []
    Generates: ['elements']
    """

    name: str = "layout"

    def __init__(self, log_level: int = logging.INFO):
        super().__init__(LayoutProcessor.name, log_level=log_level)

        self.block_graph_max_radius = 250
        self.block_vgap_threshold = 2
        self.block_vgap_start = 5
        self.block_halign_threshold = 1
        self.block_size_threshold = 2
        self.section_margin = 5
        
        self.list_regex = get_list_regex()

    def requirements(self) -> Tuple[List[str], List[str]]:
        return (["page_bounds", "image_elements", 'drawing_elements', 'text_elements'], [])

    def generates(self) -> List[str]:
        return ['elements']

    def _create_sections(self, page_bound: Bbox,
                         text: List[LineElement],
                         images: Dict[ImageType, List[ImageElement]],
                         drawings: Dict[DrawingType, List[DrawingElement]]) -> List[PageSection]:
        """Create sections based on drawn boxes, images, and page dividing lines then assign each text element to a section

        Args:
            page_bound (Bbox): Overall bbox of hte page
            text (List[LineElement]): Text elements to be assigned to sections
            images (Dict[ImageType, List[ImageElement]]): Images
            drawings (Dict[DrawingType, List[DrawingElement]]): Drawings

        Returns:
            List[PageSection]: List of page sections with text elements assigned
        """

        page_height = page_bound.height()
        page_width = page_bound.width()

        # Turn line drawings into section breaks
        breaks = [
            d.bbox for d in drawings[DrawingType.LINE]
        ]
        for line_image in images[ImageType.LINE]:
            b = line_image.bbox
            if b.y0/page_height < 0.95 and b.y0/page_height > 0.05:
                breaks.append(Bbox(max(b.x0, 0), b.y0, b.x1, b.y0+1,
                              page_bound.page_width, page_bound.page_height))
                breaks.append(Bbox(max(b.x0, 0), b.y1, b.x1, b.y1+1,
                              page_bound.page_width, page_bound.page_height))

        background = None
        if len(images[ImageType.BACKGROUND]) > 0:
            background = images[ImageType.BACKGROUND][0]

        # Split the 'default' section into chunks based on large line breaks
        sections: List[PageSection] = []
        last_y = 0.0

        for b in breaks:
            if b.width() / page_width > 0.75:
                sections.append(
                    PageSection(
                        items=[],
                        default=True,
                        backing_drawing=None,
                        backing_image=background,
                        bbox=Bbox(page_bound.x0,
                                  last_y,
                                  page_bound.x1,
                                  b.y1,
                                  page_bound.page_width,
                                  page_bound.page_height),
                        inline=True
                    )
                )
                last_y = b.y1

        # Turn remaining part of the page into final default section
        sections.append(
            PageSection(
                items=[],
                default=True,
                backing_drawing=None,
                backing_image=background,
                bbox=Bbox(page_bound.x0,
                          last_y,
                          page_bound.x1,
                          page_bound.y1,
                          page_bound.page_width,
                          page_bound.page_height),
                inline=True
            )
        )

        # Create sections from each section image
        for im in images[ImageType.SECTION]:
            sections.append(PageSection(
                bbox=Bbox(
                    im.bbox.x0+self.section_margin,
                    im.bbox.y0+self.section_margin,
                    im.bbox.x1-self.section_margin,
                    im.bbox.y1-self.section_margin,
                    page_bound.page_width,
                    page_bound.page_height
                ),
                items=[],
                default=False,
                backing_drawing=None,
                backing_image=im,
                inline=im.bbox.width() / page_width > 0.5
            )
            )

        # Create a section from each rectangle
        for drawing in drawings[DrawingType.RECT]:
            sections.append(PageSection(
                bbox=Bbox(
                    drawing.bbox.x0+self.section_margin,
                    drawing.bbox.y0+self.section_margin,
                    drawing.bbox.x1-self.section_margin,
                    drawing.bbox.y1-self.section_margin,
                    page_bound.page_width,
                    page_bound.page_height
                ),
                items=[],
                default=False,
                backing_drawing=drawing,
                backing_image=None,
                inline=drawing.bbox.width() / page_width > 0.5
            )
            )

        # Assgn lines to sections
        #sections.sort(key=lambda s: s.bbox.y0*1000 + s.bbox.x0)
        if len(sections) > 1:
            for line in text:  # type:LineElement
                written = False
                if not any(len(sp.text.strip()) > 0 for sp in line.spans):
                    continue

                for i, section in enumerate(reversed(sections[1:])):
                    if section.bbox.overlap(line.bbox, 'second') > 0.93:
                        section.append(line, update_bbox=False)
                        written = True
                        break
                if not written:
                    sections[0].append(line, update_bbox=False)
        else:
            sections[0].items += text
            
        # Filter out sections with no lines
                
        keep_sections = []
        for section in sections:
            if section.backing_image and section.backing_image.bbox.overlap(page_bound, 'second') > 0.9:
                is_page_image = True
            else:
                is_page_image = False
            if len(section.items) == 0 and not section.default and not is_page_image:
                if section.backing_image:
                    section.backing_image.type = ImageType.PRIMARY
                    images[ImageType.PRIMARY].append(section.backing_image)
            else:
                keep_sections.append(section)
                        
        self.logger.debug("Found %d section in page", len(keep_sections))
        for i, section in enumerate(keep_sections):
            self.logger.debug("Section %d - %s - %d items",
                              i+1, section.bbox, len(section.items))
            
        return keep_sections

    def _create_blocks(self, section: PageSection) -> List[TextBlock]:
        '''Group all of the items within a section into blocks'''

        blocks: List[TextBlock] = []
        block_open_state: Dict[str, bool] = {}
        section.items.sort(key=lambda l: l.bbox.y0*1000 + l.bbox.x0)
        
        for line in section.items:  # type:LineElement #type:ignore
            self.logger.debug("line: %s", line.get_text())
            self.logger.debug(line)

            used = False
            line_font = None

            for s in line.spans:
                if len(s.text.strip()) > 0:
                    line_font = s.font
                    break

            superscript = len(
                line.get_text()) < 3 and line.spans[0].font.size < 7

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

                if not block_open_state[block.element_id]:
                    continue

                self.logger.debug("block: %s", block.get_text())
                self.logger.debug(block.items[-1])

                block_font = None
                for i in range(len(block.items[-1].spans)):
                    if last_real_item.spans[-(i+1)].text.strip() != "":
                        block_font = last_real_item.spans[-(i+1)].font
                        break

                # Only allow merging with the block if it is of comparable width and
                # within the same distance as previous lines in this block

                is_bullet = self.list_regex.match(
                    line.spans[0].text.lstrip()) is not None
                line_overlap_with_block = line.bbox.x_overlap(
                    block.bbox, 'first')
                linegap = line.bbox.y0 - block.bbox.y1
                block_overlap_with_line = line.bbox.x_overlap(
                    block.bbox, 'second')
                total_overlap = line.bbox.overlap(block.bbox, 'first')

                if line_font and block_font and not superscript:
                    matched_font = abs(line_font.size - block_font.size) < 0.25 and \
                        line_font.family == block_font.family
                    matched_bold = (line_font.bold == block_font.bold) and (
                        line_font.italic == block_font.italic)
                    fuzzy_line_continuation = len(block.items) < 2 or (
                        (abs(last_real_item.bbox.x1 - block.bbox.x1) < 20) and (line.bbox.x0 - last_real_item.bbox.x0) < 2)
                    if linegap < 5:
                        matched_font = matched_font and (
                            fuzzy_line_continuation or matched_bold)
                    else:
                        matched_font = matched_font and matched_bold
                else:
                    matched_font = True

                block_linegap = 8 if len(block.items) == 1 else max(
                    block.items[1].bbox.y0 - block.items[0].bbox.y1 + 1, 3)

                self.logger.debug(f"linegap={linegap}, matched_font={matched_font}, line_overlap={line_overlap_with_block}," +
                                  f"block_overlap={block_overlap_with_line}, is_bullet={is_bullet}")

                if line_overlap_with_block > 0.08:
                    if linegap < block_linegap and matched_font and not is_bullet:
                        block.append(line)
                        self.logger.debug("Appending line to block")
                        used = True
                        continue

                    if total_overlap > 0.9:
                        block.append(line)
                        self.logger.debug(
                            "Appending line to block due to bbox overlap")
                        used = True
                        continue

                    if linegap < block_linegap and len(line.get_text().strip()) == 1 and line.spans[0].font.size < 12:
                        block.append(line)
                        self.logger.debug(
                            "Appening line to block as it's single character")
                        used = True

                    if not matched_font or is_bullet:
                        block_open_state[block.element_id] = False
                        self.logger.debug("Closing block")
                        continue

                    block_open_state[block.element_id] = False
                    self.logger.debug("Closing block")
                    continue

            if not used:
                blocks.append(TextBlock(items=[line]))
                block_open_state[blocks[-1].element_id] = True

        block_used = [False for _ in blocks]
        for i, block in enumerate(blocks):
            if block_used[i]:
                continue
            for j, b2 in enumerate(blocks[i+1:]):
                if block_used[i+j+1]:
                    continue
                if b2.bbox.overlap(block.bbox, 'first') > 0.5:
                    block.items += b2.items
                    block.items.sort(key=lambda l: l.bbox.y0*5 + l.bbox.x0)
                    block_used[i+j+1] = True

        blocks = [b for i, b in enumerate(blocks) if not block_used[i]]

        split_blocks = []
        for large_block in blocks:  # type: TextBlock
            new_blocks = []
            line_start = large_block.items[0].bbox.x0
            last_line = 0
            skip_next_i = 0
            for i, l in enumerate(large_block.items[1:-1]):
                if skip_next_i > 0:
                    skip_next_i -= 1
                    continue

                compare_to = i+2
                finish = False
                # type:ignore
                while large_block.items[compare_to].bbox.y1 < (l.bbox.y1 + 3) or len(large_block.items[compare_to].get_text()) < 3:
                    compare_to += 1
                    skip_next_i += 1

                    if compare_to == len(large_block.items):
                        finish = True
                        break
                if finish:
                    break

                if (l.bbox.x0 - line_start) > 1 and (large_block.items[compare_to].bbox.x0 - line_start) < 1:
                    new_blocks.append(
                        TextBlock(items=large_block.items[last_line:i+1])
                    )
                    last_line = i+1
                    line_start = large_block.items[compare_to].bbox.x0
                else:
                    line_start = l.bbox.x0

            if last_line > 0 and last_line != len(large_block.items) - 1:
                new_blocks.append(
                    TextBlock(items=large_block.items[last_line:])
                )
            elif last_line == 0:
                new_blocks.append(large_block)
            split_blocks += new_blocks

        self.logger.debug("Found %d blocks in section.", len(split_blocks))
        return split_blocks

    def _process(self, data: Any) -> Any:
        data['elements'] = {}
        for pn, page_bound, images, drawings, elements in self.get_page_data(data):

            # self.logger.debug(f"Computing layout for page {pn}")
            sections = self._create_sections(
                page_bound, elements, images, drawings)

            for s in sections:
                s.items = self._create_blocks(s)  # type:ignore

            data['elements'][pn] = sections

        # self.logger.debug("Finished computing layout")

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):

        colours = {
            PageSection: "Purple",
            TextBlock: "Black"
        }

        def recursive_add(fig, e):
            if isinstance(e, PageSection):
                add_rect_to_figure(fig, e.bbox, colours[PageSection])
                for i in e.items:
                    recursive_add(fig, i)
            elif isinstance(e, TextBlock):
                add_rect_to_figure(fig, e.bbox, colours[TextBlock])
            elif isinstance(e, LayoutElementGroup) or isinstance(e, list):
                for i in e:
                    recursive_add(fig, i)

        for e in data['elements'][page_number]:
            recursive_add(fig, e)

        fig.add_scatter(x=[None], y=[None], name="Section",
                        line=dict(width=3, color=colours[PageSection]))
        fig.add_scatter(x=[None], y=[None], name="Block",
                        line=dict(width=3, color=colours[TextBlock]))
