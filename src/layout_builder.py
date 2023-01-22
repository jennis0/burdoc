from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Optional
import plotly.express as plt
import fitz
from uuid import uuid4
import logging
import numpy as np
from queue import Queue

from timeit import timeit

from .bbox import Bbox
from .layout_objects import Section, Line, Block, Table, Image, Drawing
from .layout_graph import LayoutGraph



class BlockNode:
    def __init__(self, block):
        self.block = block
        self.up = None
        self.left = None
        self.up_dist = 1000
        self.left_dist = 1000
        self.right = []
        self.down = []
        self.id = uuid4()

    def intersects(self, n2):
        x_intersect = self.block.bbox.x_overlap(n2.block.bbox)
        y_intersect = self.block.bbox.y_overlap(n2.block.bbox)
        return (x_intersect, y_intersect)           



class LayoutBuilder(object):


    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.logger = logger.getChild('layoutbuilder')
        self.pdf = pdf

        self.block_graph_max_radius = 250
        self.block_vgap_threshold = 2
        self.block_vgap_start = 5
        self.block_halign_threshold = 1
        self.block_size_threshold = 2
        self.find_tables = True

    def draw_page_layout(self, page_image, items: List[Any], item_labels):

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
            'Black',
            'Crimson',
            'Green',
            'Purple',
            'Orange',
            'Pink',
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

    def _create_sections(self, page: fitz.Page, text : List[Line], images : List[Image], drawings : List[Drawing]) -> List[Section]:

        page_bbox = Bbox(*page.bound())
        page_height = page_bbox.height()
        page_width = page_bbox.width()

        breaks = [
            d.bbox for d in drawings['Line']
        ]
        for line in images['Line']:
            b = line.bbox
            if b.y0/page_height < 0.95 and b.y0/page_height > 0.05:
                breaks.append(Bbox(max(b.x0,0), b.y0, b.x1, b.y0+1))
                breaks.append(Bbox(max(b.x0,0), b.y1, b.x1, b.y1+1))

        background = None
        if len(images['Background']) > 0:
            background = images['Background'][0]

        small_breaks = []
        sections = []
        last_y = 0
        for b in breaks:
            if b.width() / page_width > 0.75:
                sections.append(
                        Section(
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

        sections.append(
            Section(
                items=[], 
                default=True, 
                backing_drawing=None, 
                backing_image=background, 
                bbox=page_bbox.clone(),
                inline=True
            )
        )
        sections[-1].bbox.y0 = last_y

    
        for i in images['Section']:
            sections.append(Section(
                    bbox=i.bbox.clone(), 
                    items=[], 
                    default=False, 
                    backing_drawing=None, 
                    backing_image=i,
                    inline = i.bbox.width() / page_width > 0.5
                )
            )

        for d in drawings['Rect']:
            sections.append(Section(
                    bbox=d.bbox.clone(), 
                    items=[], 
                    default=False, 
                    backing_drawing=d, 
                    backing_image=None,
                    inline = d.bbox.width() / page_width > 0.5
                )
            )

        for linebreak in small_breaks:
            if linebreak.is_vertical():
                continue
            for i, sec in enumerate(sections):
                written=False
                if sec.bbox.overlap(linebreak, 'second') > 0.99:
                    sec.items.append(Line(bbox=linebreak, type=Line.LineType.Break, spans=[]))
                    written = True
                    break
            if not written:
                sections[0].items.append(Line(bbox=linebreak, type=Line.LineType.Break, spans=[]))

        sections.sort(key=lambda s: s.bbox.y0*10000 + s.bbox.x0)
        if len(sections) > 1:
            for l in text:
                written = False
                if not any(len(sp.text.strip()) > 0 for sp in l.spans):
                    continue
                
                for i,s in enumerate(sections[1:]):
#                    print(i, l.spans[0].text, s.bbox.overlap(l.bbox, 'second'))
                    if s.bbox.overlap(l.bbox, 'second') > 0.99:
                        s.items.append(l)
                        written = True
                        break
                if not written:
                    sections[0].items.append(l)
        else:
            sections[0].items += text

        sections = [s for s in sections if len(s.items) > 0]
        for s in sections:
            s.items.sort(key=lambda l: l.bbox.x0 + l.bbox.y0 * 1000)

        self.logger.debug(f"Found {len(sections)} section in page")
        for i,s in enumerate(sections):
            self.logger.debug(f"Section {i+1} - {s.bbox} - {len(s.items)} items")

        return sections

    def _create_blocks(self, section: Section) -> List[Block]:
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
                    alignments[Block.Alignment.left] = \
                        abs(block.bbox.x0 - line.bbox.x0) < self.block_halign_threshold
                    alignments[Block.Alignment.right] = \
                        abs(block.bbox.x1 - line.bbox.x1) < self.block_halign_threshold
                    alignments[Block.Alignment.center] = \
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
                    Block(
                        type=Block.BlockType.Text,
                        lines=[line], 
                        bbox=line.bbox, 
                        fonts=fonts,
                        alignment={Block.Alignment.left: True, Block.Alignment.right: True, Block.Alignment.center: True}, 
                        open=True,
                        lineheight=self.block_vgap_start
                    ))
                    
        self.logger.debug(f"Found {len(blocks)} blocks in section.")            
        return blocks

    def _create_block_graph(self, blocks: List[Block]) -> List[BlockNode]:
        self.logger.debug("Creating block graph")

        blocks.sort(key = lambda c: c.bbox.y0 * 100 + c.bbox.x0)
        nodes = [BlockNode(b) for b in blocks]
        for i,n1 in enumerate(nodes):
            for j,n2 in enumerate(nodes):
                if i == j:
                    continue

                x_distance = n2.block.bbox.x_distance(n1.block.bbox)
                y_distance = n2.block.bbox.y_distance(n1.block.bbox)
                x,y = n1.intersects(n2)
                x /= n1.block.bbox.width()
                y /= n1.block.bbox.height()

                if abs(x_distance) > self.block_graph_max_radius:
                    continue
                if abs(y_distance) > self.block_graph_max_radius:
                    continue
                if x_distance < 0 and y_distance < 0:
                    continue

                if self.logger.level == logging.DEBUG:
                    self.logger.debug("\t", n2.block.lines[0].spans[0].text, 
                        "x:",round(x_distance,2), "y:", round(y_distance,2), "ix:", x, "iy:", y)

                if x > 0.01 and y < 0.05:
                    if y_distance >= 0 and y_distance < n1.up_dist:
                        n1.up = n2
                        n1.up_dist = y_distance
                if y > 0.01 and x < 0.05:
                    if x_distance >= 0 and x_distance < n1.left_dist:
                        n1.left = n2
                        n1.left_dist = x_distance


            if n1.up:
                n1.up.down.append(n1)
            if n1.left:
                n1.left.right.append(n1)

        for n1 in nodes:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(n1.block)
                self.logger.debug("-------------------------------------")
                if n1.up:
                    self.logger.debug(u"\tUp:" + str(n1.up.block))
                else:
                    self.logger.debug(u"\tUp: None")
                if n1.left:
                    self.logger.debug(u"\tLeft:" + str(n1.left.block))
                else:
                    self.logger.debug("\tLeft: None")
            
                for n in n1.down:
                    self.logger.debug(u"\tDown:" + str(n.block))

                for n in n1.right:
                    self.logger.debug(u"\tRight:" + str(n.block))

                self.logger.debug("=====================================")

        self.logger.debug("Finished creating block graph")
        return nodes

    def _generate_table_candidates(self, blocks: List[Block]) -> List[List[List[BlockNode]]]:
        print("Old:", timeit(lambda :self._create_block_graph(blocks), number=1000)/1000)
        blocknodes = self._create_block_graph(blocks)

        used_nodes = {b.id:False for b in blocknodes}

        blocknodes.sort(key=lambda bn: bn.block.bbox.y0*5 + bn.block.bbox.x0)

        tables = []

        for b in blocknodes:
            if used_nodes[b.id]:
                continue

            if len(b.block.lines) == 0 or len(b.block.lines[0].spans) == 0:
                continue

            columns = [[b]]
            candidate = b

            self.logger.debug(f"Starting table search with seed {b.block}")

            if len(candidate.right) == 0:
                self.logger.debug(f"Skipping as seed due to no rightward text")
                continue

            col_edge = min([1000] + [c.block.bbox.x0 for c in candidate.right])

            if abs(candidate.right[0].block.bbox.y0 - candidate.block.bbox.y0) > 20:
                self.logger.debug(f"Skipping as seed as no aligned right text")
                continue

            #Build first row by pushing as far down as possible in a straight line
            while(True):
                
                if len(candidate.down) != 1:
                    break
                
                self.logger.debug(f"Considering {candidate.down[0].block} for first row")
                
                if candidate.down[0].block.bbox.x1 > col_edge:
                    self.logger.debug(f"Skipping as it hits column edge")
                    break

                candidate = candidate.down[0]
                columns[0].append(candidate)

            self.logger.debug(f"{str(b.block)} - {len(columns[0])} candidate row blocks")

            #Build header row by pushing as far across as possible
            col_top = b.block.bbox.y0
            col_bottom = columns[0][-1].block.bbox.y1
            fontsize = b.block.lines[0].spans[0].font.size
            candidate = columns[0][0].right[0]
            while (True):
                self.logger.debug(f"Considering {candidate.block} for header row")

                if len(candidate.block.lines) == 0 or len(candidate.block.lines[0].spans) == 0:
                    self.logger.debug(f"Skipping as empty")
                    break
                if abs(candidate.block.lines[0].spans[0].font.size - fontsize) > 0.0:
                    self.logger.debug(f"Skipping due to font mismatch")
                    break
                if abs(candidate.block.bbox.y0 - col_top) > 20:
                    self.logger.debug(f"Skipping as column would be too large")
                    break

                columns.append([candidate])

                if len(candidate.right) > 0:
                    if candidate.right[-1].block.bbox.y1 - col_bottom > 20:
                        break

                    candidate = candidate.right[0]
                else:
                    break

            self.logger.debug(f"{str(b.block)} - {len(columns)} candidate columns")

            if len(columns) < 2:
                continue

            column_bboxes = [Bbox.merge(n.block.bbox for n in columns[0])]

            for i,col in enumerate(columns[1:]):
                n = col[0]
                prev_boundary = column_bboxes[i].x1
                next_boundary = columns[i+2][0].block.bbox.x0 if len(columns) >= i+3 else 100000
                if len(n.down) > 0:
                    candidate = n.down[0]
                    
                    while(True):
                        if candidate.block.bbox.x0 < prev_boundary or candidate.block.bbox.x1 > next_boundary:
                            break
                        
                        if candidate.block.bbox.y0 - col[-1].block.bbox.y1 > 30:
                            break

                        if candidate.block.bbox.y1 <= col_bottom + 200:
                            col.append(candidate)
                            if len(candidate.down) >= 1:
                                candidate = candidate.down[0]
                                continue
                        
                        break
                
                self.logger.debug(f"Added {len(col) - 1} blocks to column {i+1}")
                column_bboxes.append(Bbox.merge(n.block.bbox for n in col))


            for i,c in enumerate(column_bboxes[1:]):
                self.logger.debug(f"{column_bboxes[0].y1} {c.y1}")
                if column_bboxes[0].y1 - c.y1 > 20:
                    columns = columns[:i+1]
            
            self.logger.debug(f"Filtered to {len(columns)} columns")        
                    
            if len(columns) < 2:
                continue

            

            for col in columns:
                for n in col:
                    used_nodes[n.id] = True


            # print("=======================================================")
            # for col in columns:
            #     for n in col:
            #         print(n.block, n.block.bbox)
            #     print("---------------------------------------------------")
            # print("=======================================================")
            # print()

            tables.append(columns)

        return tables

    def _create_table_from_candidate(self, candidate: List[List[BlockNode]]) -> Optional[Table]:
        #Generate bounding box for table
        dims = candidate[0][0].block.bbox
        for col in candidate:
            for n in col:
                dims = Bbox.merge([dims, n.block.bbox])

        #Build array from individual lines so we can look for gaps
        arr = np.zeros(shape=(int(dims.y1 - dims.y0), int(dims.x1 - dims.x0)))
        for col in candidate:
            for b in col:
                for n in b.block.lines:
                    arr[
                        int(n.bbox.y0 - dims.y0):int(n.bbox.y1 - dims.y0),
                        int(n.bbox.x0 - dims.x0):int(n.bbox.x1 - dims.x0),
                        
                    ] = 1

        #Do the same for the first column to enable later comparisons - note we use
        #block granularity not line granularity to minimise possible number
        c1_arr = np.zeros(shape=(int(dims.y1 - dims.y0), int(dims.x1 - dims.x0)))
        for b in candidate[0]:
            c1_arr[
                int(b.block.bbox.y0 - dims.y0):int(b.block.bbox.y1 - dims.y0),
                int(b.block.bbox.x0 - dims.x0):int(b.block.bbox.x1 - dims.x0),
                
            ] = 1
      
        #Calculate all of the possible horizontal lines
        horizontal_array = np.zeros(arr.shape)
        horizontal_array = arr.sum(axis=1) == 0

        h_lines = []
        current_run = -1
        current_run_length = 0
        for i,v in enumerate(horizontal_array):
            if v > 0.5:
                if current_run >= 0:
                    current_run_length += 1
                else:
                    current_run_length = 1
                    current_run = i
            else:
                if current_run >= 0:
                    h_lines.append((current_run, current_run_length))
                    current_run = -1

        if current_run >= 0:
            h_lines.append((current_run, current_run_length))

        #Calculate all of the possible horizontal lines for the first column
        c1_horizontal_array = np.zeros(c1_arr.shape)
        c1_horizontal_array = c1_arr.sum(axis=1) == 0

        c1_h_lines = []
        current_run = -1
        current_run_length = 0
        for i,v in enumerate(c1_horizontal_array):
            if v > 0.5:
                if current_run >= 0:
                    current_run_length += 1
                else:
                    current_run_length = 1
                    current_run = i
            else:
                if current_run >= 0:
                    c1_h_lines.append((current_run, current_run_length))
                    current_run = -1

        if current_run >= 0:
            c1_h_lines.append((current_run, current_run_length))

        #Typically expect consistent numbers, especially given the first col is using blocks
        #Only expect to see more in first col when it is plain text and we're picking up 
        #block breaks
        if len(c1_h_lines) >= 2*len(h_lines):
            return None


        #Filter line breaks out of low density tables
        self.logger.debug(f"Found line candidates - {h_lines}")
        line_width = np.max([h[1] for h in h_lines])
        if line_width > 4:
            self.logger.debug("Filtering lines from low density table")
            h_lines = [h[0] + h[1]/2 + dims.y0 for h in h_lines if h[1] >= 3] + [100000]
        else:
            h_lines = [h[0] + h[1]/2 + dims.y0 for h in h_lines] + [100000]


        if len(h_lines) < 2:
            return None

        #Not a table if a single cell takes up a huge quantity of a page.        
        h_dists = []
        for i in range(1, len(h_lines)-1):
            h_dists.append(h_lines[i] - h_lines[i-1])
        if any(h > 300 for h in h_dists):
            return None

        # vertical_array = np.zeros(arr.shape)
        # vertical_array = arr.sum(axis=0) == 0
        # ah = np.repeat(horizontal_array[:,np.newaxis], arr.shape[1], axis=1)
        # av = np.repeat(vertical_array[np.newaxis,:], arr.shape[0], axis=0)
        # fig = plt.imshow(5*(ah + av) + arr)
        # fig.show()

        #Position lines within cells
        cells = []
        for i,col in enumerate(candidate):
            current_h_line = 0
            cells.append([])
            current_cell = []
            for bn in col:
                for line in bn.block.lines:
                    while line.bbox.y0 >= h_lines[current_h_line]:
                        if i == 0 and len(current_cell) == 0:
                            return None
                        cells[-1].append(current_cell)
                        current_cell = []
                        current_h_line += 1
                    current_cell.append(line)
            cells[-1].append(current_cell)

        #Throw away tables with mismatched columns - usually means not a real table!
        lengths = [len(col) for col in cells]
        max_len = max(lengths)
        if any((l - max_len) != 0 for l in lengths):
            return None

        # print("=================================================================")
        # for c in cells:
        #     for v in c:
        #         for block in v:
        #             print(block)
        #         print()
        #     print("------------------------------------------------------------")
        # print("=================================================================")

        if cells[0][0][0].spans[0].font.bold:
            headers = [c[0] for c in cells]
            cells = [c[1:] for c in cells]
            return Table(dims, headers, cells)
        
        return Table(dims, None, cells)

    def _find_tables(self, blocks: List[Block]) -> List[Block]:

        candidates = self._generate_table_candidates(blocks)
        tables = []
        for cand in candidates:
            tab = self._create_table_from_candidate(cand)
            if tab:
                tables.append(tab)

        revised_blocks = []
        for block in blocks:
            used = False
            for t in tables:
                if block.bbox.overlap(t.bbox, 'first') > 0.5:
                    used = True
                    break
            if not used:
                revised_blocks.append(block)
        revised_blocks += tables

        return revised_blocks
            
    def _flow_content(self, page: fitz.Page, sections: List[Section], images: List[Image]):

            def columnise(items):
                cols = []
                items.sort(key=lambda i: i.bbox.y0*1000 + i.bbox.center().x)
                for i in items:
                    used = False
                    for c in cols:
                        if not c[2]:
                            continue
                        if i.bbox.x0 < c[1].x0 - 10:
                            c[2] = False
                            continue
                        if c[1].width()/page_bound.width() < 0.5:
                            if len(c[0]) > 2 and i.bbox.width()/page_bound.width() > 0.5:
                                c[2] = False
                                continue
                        else:
                            if i.bbox.width()/page_bound.width() < 0.5:
                                c[2] = False
                                continue
                        if i.bbox.x_overlap(c[1], 'first') > 0.05:
                            c[0].append(i)
                            c[1] = Bbox.merge([c[1], i.bbox])
                            used = True
                            break
                        
                    if not used:
                        cols.append([[i], i.bbox.clone(), True])

                cols.sort(key=lambda c: c[1].y0*100 + c[1].x0)
                return cols

            page_bound = Bbox(*page.bound())
            flow_sections = []
            used_images = [False for i in images]
            for section in sections:
                if section.default:
                    continue

                for i,im in enumerate(images):
                    if used_images[i]:
                        continue
                    if im.bbox.overlap(section.bbox) > 0.5:
                        section.items.append(im)
                        used_images[i] = True

                section.items = columnise(section.items)
                flow_sections.append(section)

            used_sections = [False for f in flow_sections]
            complete_sections = []
            for section in sections:
                if not section.default:
                    continue

                for i,im in enumerate(images):
                    if used_images[i]:
                        continue
                    if im.bbox.overlap(section.bbox) > 0.5:
                        section.items.append(im)
                        used_images[i] = True

                for i,f in enumerate(flow_sections):
                    if used_sections[i]:
                        continue
                    if f.bbox.overlap(section.bbox) > 0.75:
                        section.items.append(f)
                        used_sections[i] = True

                section.items = columnise(section.items)
                complete_sections.append(section)

            for i,f in enumerate(flow_sections):
                if not used_sections[i]:
                    complete_sections.append(f)
                
            for s in complete_sections:
                for col in s.items:
                    for item in col[0]:
                        print(item, item.bbox.width())
                    print("--------------------------------")
                print("==========================================")
            

    def compute_layout(self, page: fitz.Page, text: List[Any], images, drawings, page_image):

        self.logger.debug("Computing layout")
        sections = self._create_sections(page, text, images, drawings)
        for s in sections:
            blocks = self._create_blocks(s)

            lg = LayoutGraph(self.logger, page.bound(), blocks)
            print(lg)
            # s.items = blocks
            # if self.find_tables:
            #     s.items = self._find_tables(blocks)

            self.draw_page_layout(
                page_image, 
                [
                    #images['Primary'],
                    #images['Section'],
                    #images['Line'],
                    #drawings['Line'], 
                    #drawings['Rect'], 
                    #s.items, 
                    [s], 
                    blocks,
                    #tables
                ],
                [
                    #'Primary Image',
                    #'Section Image',
                    #'Line Image',
                    #'Line Drawing',
                    #'Rect Drawing',
                     #'Line', 
                    'Section',
                    'Block',
                    #'Table'
                ]
            )

        # self._flow_content(page, sections, images['Primary'])

        self.logger.debug("Finished computing layout")