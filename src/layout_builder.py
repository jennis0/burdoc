from typing import Any, List
import plotly.express as plt
import fitz
import logging

from .bbox import Bbox
from .layout_objects import LSection, LLine, LBlock, LTable, LImage, LDrawing, LayoutElement
from .table_generator import TableGenerator


class LayoutBuilder(object):

    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.logger = logger.getChild('layoutbuilder')
        self.pdf = pdf

        self.block_graph_max_radius = 250
        self.block_vgap_threshold = 2
        self.block_vgap_start = 5
        self.block_halign_threshold = 1
        self.block_size_threshold = 2
        self.section_margin = 5
        self.find_tables = True

    def draw_page_layout(self, page_image, items: List[List[LayoutElement]], item_labels: List[str]):
        '''Render an image of the page to the screen, highlighting elements'''

        def add_rect(fig, bbox: Any, colour: str, width: int=3):
            fig.add_shape(
                dict(
                    type='rect', xref='x', yref='y', opacity=0.6,
                    x0=bbox.x0, x1=bbox.x1, y0=bbox.y0, y1=bbox.y1,
                    line=dict(color=colour, width=width)
                )
            )

        COLOURS=[
            'Grey',
            'RoyalBlue',
            'Crimson',
            'Green',
            'Purple',
            'Orange',
            'Pink',
            'Black',
            'Cyan',
            
        ]

        fig = plt.imshow(page_image)
        for (item_list, label, colour) in zip(items, item_labels, COLOURS):
            for i in item_list:
                add_rect(fig, i.bbox, colour)
            
            fig.add_scatter(
                x=[None],
                y=[None],
                name=label,
                line=dict(width=3, color=colour),
            ),

        fig.update_layout({'showlegend': True, 'height':1000, 'xaxis':{'showticklabels':False}, 'yaxis':{'showticklabels':False}})
        fig.show()

    def _create_sections(self, page: fitz.Page, text : List[LLine], images : List[LImage], drawings : List[LDrawing]) -> List[LSection]:
        '''Create sections based on drawn boxes, images, and page dividing lines then assign each text element to a section'''

        bound = page.bound()
        page_bbox = Bbox(*bound, bound[2], bound[3])
        page_height = page_bbox.height()
        page_width = page_bbox.width()

        #Turn line drawings into section breaks
        breaks = [
            d.bbox for d in drawings['Line']
        ]
        for line in images['Line']:
            b = line.bbox
            if b.y0/page_height < 0.95 and b.y0/page_height > 0.05:
                breaks.append(Bbox(max(b.x0,0), b.y0, b.x1, b.y0+1, bound[2], bound[3]))
                breaks.append(Bbox(max(b.x0,0), b.y1, b.x1, b.y1+1, bound[2], bound[3]))

        background = None
        if len(images['Background']) > 0:
            background = images['Background'][0]

        #Create a section from each line break
        small_breaks = []
        sections = []
        last_y = 0
        for b in breaks:
            if b.width() / page_width > 0.75:
                sections.append(
                        LSection(
                        items=[],
                        default=True,
                        backing_drawing=None,
                        backing_image=background,
                        bbox = page_bbox.clone(),
                        inline=True
                    )
                )
                sections[-1].bbox.y0 = last_y
                sections[-1].bbox.y1 = b.y1
                last_y = b.y1
            else:
                small_breaks.append(b)

        #Create a default section
        sections.append(
            LSection(
                items=[], 
                default=True, 
                backing_drawing=None, 
                backing_image=background, 
                bbox=page_bbox.clone(),
                inline=True
            )
        )
        sections[-1].bbox.y0 = last_y

        #Create sections from each section image
        for i in images['Section']:
            sections.append(LSection(
                    bbox=Bbox(
                        i.bbox.x0+self.section_margin, 
                        i.bbox.y0+self.section_margin, 
                        i.bbox.x1-self.section_margin, 
                        i.bbox.y1-self.section_margin,
                        page_bbox.page_width,
                        page_bbox.page_height), 
                    items=[], 
                    default=False, 
                    backing_drawing=None, 
                    backing_image=i,
                    inline = i.bbox.width() / page_width > 0.5
                )
            )

        #Create a section from each rectangle
        for d in drawings['Rect']:
            sections.append(LSection(
                    bbox=Bbox(
                        d.bbox.x0+self.section_margin,
                        d.bbox.y0+self.section_margin, 
                        d.bbox.x1-self.section_margin, 
                        d.bbox.y1-self.section_margin,
                        page_bbox.page_width,
                        page_bbox.page_height),  
                    items=[], 
                    default=False, 
                    backing_drawing=d, 
                    backing_image=None,
                    inline = d.bbox.width() / page_width > 0.5
                )
            )

        #Divide sections based on small breaks
        for linebreak in small_breaks:
            if linebreak.is_vertical():
                continue
            for i, sec in enumerate(sections[1:]):
                written=False
                if sec.bbox.overlap(linebreak, 'second') > 0.97:
                    sec.items.append(LLine(bbox=linebreak, type=LLine.LineType.Break, spans=[]))
                    written = True
                    break
                if not written:
                    sections[0].items.append(LLine(bbox=linebreak, type=LLine.LineType.Break, spans=[]))

        #Assgn lines to sections
        sections.sort(key=lambda s: s.bbox.y0*10000 + s.bbox.x0)
        if len(sections) > 1:
            for l in text:
                written = False
                if not any(len(sp.text.strip()) > 0 for sp in l.spans):
                    continue
                
                for i,s in enumerate(sections[1:]):
                    if s.bbox.overlap(l.bbox, 'second') > 0.97:
                        s.items.append(l)
                        written = True
                        break
                if not written:
                    sections[0].items.append(l)
        else:
            sections[0].items += text

        #Filter out sections with no lines
        sections = [s for s in sections if len(s.items) > 0]

        self.logger.debug(f"Found {len(sections)} section in page")
        for i,s in enumerate(sections):
            self.logger.debug(f"Section {i+1} - {s.bbox} - {len(s.items)} items")

        return sections

    def _create_blocks(self, section: LSection) -> List[LBlock]:
        '''Group all of the items within a section into blocks'''
        blocks = []
        for line in section.items:

            used = False
            fonts = [s.font for s in line.spans]
            
            for block in blocks:
                if not block.open:
                    continue

                ### Only allow merging with the block if it is of comparable width and
                ### within the same distance as previous lines in this block
                widthgap = abs(line.bbox.width() / block.bbox.width())
                linegap = line.bbox.y0 - block.bbox.y1
                if widthgap < 2 and linegap < block.lineheight + self.block_vgap_threshold:

                    ### Only allow merging if it shares a font with a line already int he block
                    matched_size = False
                    new_fonts = []
                    for f in fonts:
                        for f2 in block.fonts:
                            if f.family == f2.family and abs(f.size - f2.size) < self.block_size_threshold:
                                matched_size = True
                            else:
                                new_fonts.append(f)
                    if len(fonts) > 0 and not matched_size:
                        continue

                    ### Only allow merging with a block if the alignment is compatible
                    alignments = {}
                    alignments[LBlock.Alignment.left] = \
                        abs(block.bbox.x0 - line.bbox.x0) < self.block_halign_threshold
                    alignments[LBlock.Alignment.right] = \
                        abs(block.bbox.x1 - line.bbox.x1) < self.block_halign_threshold
                    alignments[LBlock.Alignment.center] = \
                        abs(block.bbox.center().x - line.bbox.center().x) < 2*self.block_halign_threshold
                    
                    for a in alignments:  
                        if alignments[a] and block.alignment[a]:
                            block.lineheight = linegap
                            block.lines.append(line)
                            block.alignment = {i:alignments[i] and block.alignment[i] for i in alignments}
                            block.bbox = Bbox.merge([block.bbox, line.bbox])
                            block.fonts += new_fonts
                            used = True
                            break
                            
                ### Close blocks that this line is close to if we don't merge
                if not used and line.bbox.x_overlap(block.bbox):
                    block.open = False

            if not used:
                blocks.append(
                    LBlock(
                        type=LBlock.BlockType.Text,
                        lines=[line], 
                        bbox=line.bbox, 
                        fonts=fonts,
                        alignment={LBlock.Alignment.left: True, LBlock.Alignment.right: True, LBlock.Alignment.center: True}, 
                        open=True,
                        lineheight=self.block_vgap_start
                    ))
                    
        self.logger.debug(f"Found {len(blocks)} blocks in section.")            
        return blocks

    def _find_tables(self, page: fitz.Page, section: LSection) -> List[LTable]:
        '''Find all of the tables within a section'''
        tg = TableGenerator(self.logger)
        tables = tg.find_tables(page, section.items)

        revised_blocks = []
        for block in section.items:
            used = False
            for t in tables:
                if block.bbox.overlap(t.bbox, 'first') > 0.5:
                    used = True
                    break
            if not used:
                revised_blocks.append(block)

        return revised_blocks + tables

            
    def _flow_items(self, page_bound: Bbox, elements: List[LayoutElement]):
        
        elements.sort(key=lambda e: e.bbox.y0*100 + e.bbox.x0)
        page_width = page_bound.width()
        center = page_bound.center()

        columns = []
        for e in elements:
            used = False
            self.logger.debug(e)
            for c in columns:
                if not c[2]:
                    continue

                c_full_page = c[0].width() / page_width > 0.6
                e_full_page = e.bbox.width() / page_width > 0.6
                l_aligned = abs(c[0].x0 - e.bbox.x0) < 2
                c_centered = abs(c[0].center().x - center.x) < 10
                e_centered = abs(e.bbox.center().x - center.x) < 10

                dy = e.bbox.y0 - c[0].y1
                dx_col= c[0].x_overlap(e.bbox, 'first')
                dx_block = c[0].x_overlap(e.bbox, 'second')
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
                if not stop and not append and c[0].x0 < e.bbox.center().x:
                    if abs(dy) < 15:
                        if dx_col > (0.1 if not c_full_page else 0.5) :
                            append = True
                    elif abs(dy) < 30:
                        if dx_col > 0.6:
                            append = True
                
                if append:
                    c[1].append(e)
                    c[0] = Bbox.merge([c[0], e.bbox])
                    used = True
                    self.logger.debug("Appended")
                    break
                elif dx_col > 0.1:
                    c[2] = False
                    self.logger.debug("Closing column")


            if not used:
                columns.append(
                    [e.bbox.clone(), [e], True]
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
                if columns[i][0].overlap(columns[j][0], 'min') > 0.5:
                    columns[i][0] = Bbox.merge([columns[i][0], columns[j][0]])
                    columns[i][1] += columns[j][1]
                    columns[i][1].sort(key=lambda e: e.bbox.y0*100 + e.bbox.x0) 
                    remove_cols.add(j)
        columns = [c for i,c in enumerate(columns) if i not in remove_cols]
        self.logger.debug(f"Removing columns {remove_cols}")

        #Sort lines within columns
        for c in columns:
            c[1].sort(key=lambda e: e.bbox.y0*100 + e.bbox.x0)

        columns.sort(key=lambda c: c[0].y0*100 + c[0].x0)
        self.logger.debug(f"Found {len(columns)} columns")

        return [LSection(c[0], c[1]) for c in columns]
                    

        
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
            s.sort(key=lambda c: round(c.bbox.y0/5, 0) * 1000 + c.bbox.x0)
            sorted += s
        return sorted


    def _flow_content(self, page: fitz.Page, sections: List[LSection], images: List[LImage]):

        bound = page.bound()
        page_bound = Bbox(*bound, bound[2], bound[3])
        default_sections = [s for s in sections if s.default]
        other_sections = [s for s in sections if not s.default]

        used_images = set()

        for s in other_sections:
            
            inline_images = []
            outline_images = []
            for i,im in enumerate(images):
                if i in used_images:
                    continue
                if im.bbox.overlap(s.bbox, 'first') > 0.9:
                    overlap = 0
                    for block in s.items:
                        overlap += im.bbox.overlap(block.bbox, 'first')
                    if overlap > 0.2:
                        outline_images.append(LSection(im.bbox, [im]))
                    else:
                        inline_images.append(im)
                    used_images.add(i)
                        
            columns = self._flow_items(page_bound, s.items + inline_images)
            columns = self._flow_columns(page_bound, columns + outline_images)

            for d in default_sections:
                if s.bbox.overlap(d.bbox, 'first'):
                    d.items.append(s)

        complete_sections = []
        for s in default_sections:

            inline_images = []
            outline_images = []
            for i,im in enumerate(images):
                if i in used_images:
                    continue
                if im.bbox.overlap(s.bbox, 'first') > 0.9:
                    overlap = 0
                    for block in s.items:
                        overlap += im.bbox.overlap(block.bbox, 'first')
                    if overlap > 0.2:
                        outline_images.append(LSection(im.bbox, [im]))
                    else:
                        inline_images.append(im)
                    used_images.add(i)

            columns = self._flow_items(page_bound, s.items + inline_images)

            # print(columns)
            # print()
            # print(outline_images)
            # print()

            columns = self._flow_columns(page_bound, columns + outline_images)
            complete_sections.append(columns)

        #Merge images with sections
        for i,im in enumerate(images):
            if i not in used_images:
                complete_sections.append([LSection(im.bbox, [im])])

        return complete_sections


    def compute_layout(self, page: fitz.Page, text: List[Any], images, drawings, page_image):

        self.logger.debug("Computing layout")
        sections = self._create_sections(page, text, images, drawings)
        for s in sections:
            s.items = self._create_blocks(s)
            if self.find_tables:
                s.items = self._find_tables(page, s)

        # self.draw_page_layout(
        #     page_image, 
        #     [
        #         images['Primary'],
        #         # images['Section'],
        #         #images['Line'],
        #         #drawings['Line'], 
        #         #drawings['Rect'], 
        #         text, 
        #         sections,
        #         #blocks,
        #         tables
        #     ],
        #     [
        #         'Primary Image',
        #         # 'Section Image',
        #         #'Line Image',
        #         #'Line Drawing',
        #         #'Rect Drawing',
        #         'Line', 
        #         'Section',
        #         #'Block',
        #         'Table'
        #     ]
        # )

        ordered_content = self._flow_content(page, sections, images['Primary'])

        self.logger.debug("Finished computing layout")
        return ordered_content