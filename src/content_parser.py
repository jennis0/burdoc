import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from uuid import uuid4

from .layout_objects import LayoutElement,LSection, LLine, LBlock, LTable, LImage
from .content_objects import CSpan, CParagraph, CTitle, CImage, CTable, CAside, CHeaderFooter

import numpy as np
import plotly.express as plt


class ContentParser(object):

    def __init__(self, logger: logging.Logger):
        self.logger = logger.getChild('contentparser')
        self.text_bins = None
        self.page_meta = {}

    def fit_font_predictor(self, font_statistics):
        counts = {}
        for family in font_statistics:
            for size in font_statistics[family]['_counts']:
                if size not in counts:
                    counts[size] = font_statistics[family]['_counts'][size]
                else:
                    counts[size] += font_statistics[family]['_counts'][size]

        arr = np.zeros(shape=(int(max(counts.keys())+1)))
        for c in counts:
            arr[int(c)] += counts[c]

        arr /= arr.sum()
        paragraph_index = arr.argmax()

        bins = []
        current_bin = None
        text_bin_index = 0
        for i,a in enumerate(arr):
            if current_bin == None:
                if a > 0.0:
                    current_bin = [i,i+1]
                    if i == paragraph_index:
                        text_bin_index = len(bins)
            else:
                if a > 0.0:
                    current_bin[1] = i+1
                    if i == paragraph_index:
                        text_bin_index = len(bins)
                else:
                    bins.append(current_bin)
                    current_bin = None
        if current_bin:
            bins.append(current_bin)

        arr = np.zeros(shape=arr.shape, dtype=np.int8)
        arr -= 16
        for i,b in enumerate(bins):
            arr[b[0]:b[1]] = i - text_bin_index

        self.text_bins = arr

    def get_text_class(self, span: CSpan):
        return self.text_bins[int(span.font.size)]

    def parse_block(self, block: LBlock, last_element: LayoutElement, last_parsed: Any) -> List[Any]:
        current_class = None

        line_start = 0
        line_end = len(block.lines)
        if block.bbox.y0_norm() < 0.05:
            header = CParagraph([])
            for line in block.lines:
                if line.bbox.y1_norm() < 0.05:
                    header.lines.append(line.spans)
                    line_start += 1
                else:
                    break
            self.page_meta['header'].paras.append(header)
        
        if block.bbox.y1_norm() > 0.95:
            footer = CParagraph([])
            for i in range(len(block.lines)):
                line = block.lines[-(i+1)]
                if line.bbox.y0_norm() > 0.95:
                    footer.lines.append(line.spans)
                    line_end -=1
                else:
                    break
            self.page_meta['footer'].paras.append(footer)
                
        block.lines = block.lines[line_start:line_end]

        if last_element and isinstance(last_parsed, CParagraph) and abs(block.bbox.y0 - last_element.bbox.y1) < 1:
            paras = [last_parsed]
            strip_first = True
            if isinstance(last_element, LBlock):
                current_class = self.get_text_class(last_element.lines[0].spans[0])
        else:
            paras = []
            strip_first = False
            
        for line in block.lines:
            if len(line.spans) == 0:
                continue
            cl = self.get_text_class(line.spans[0])
            if cl == current_class:
                if isinstance(paras[-1], CTitle):
                    paras[-1].spans += line.spans
                else:
                    if len(paras) == 0:
                        paras.append(CParagraph([line.spans]))
                    else:
                        paras[-1].lines.append(line.spans)
            else:
                if cl > 0:
                    paras.append(CTitle(uuid4(), line.spans, cl))
                else:
                    paras.append(CParagraph([line.spans]))
            current_class = cl

        if strip_first:
            paras = paras[1:]
        return paras

    def parse_table(self, table: LTable, last_element: LayoutElement, last_parsed: Any) -> List[CTable]:
        ctable = CTable([], [], None, None)
        if table.headers:
            for h in table.headers:
                ctable.headers.append(CParagraph([l.spans for l in h]))

            for row in table.values:
                ctable.values.append([])
                for column in row:
                    ctable.values[-1].append(CParagraph([l.spans for l in column]))

        return [ctable]
                
    def parse_section(self, section):
        parsed = []
        last_element = None
        last_parsed = None

        for element in section.items:
            if isinstance(element, LSection):
                parsed += self.parse_section(element)

            elif isinstance(element, LImage):
                parsed.append(CImage(element, None))

            elif isinstance(element, LBlock):
                parsed += self.parse_block(element, last_element, last_parsed)

            elif isinstance(element, LTable):
                parsed += self.parse_table(element, last_element, last_parsed)

            last_element = element
            if len(parsed) > 0:
                last_parsed = parsed[-1]

        if not section.default and (section.backing_image or section.backing_drawing) :
            return [CAside(parsed)]
        else:
            return parsed

    def parse_page(self, elements: List[List[LayoutElement]]) -> Any:
        last_element_y1 = 0.0
        parsed = []

        self.page_meta['header'] = CHeaderFooter([])
        self.page_meta['footer'] = CHeaderFooter([])
        for section in elements:
            for column in section:
                parsed += self.parse_section(column)

        text = self.page_meta['header'].to_html()
        for p in parsed:
            text += p.to_html()
        text += self.page_meta['footer'].to_html()

        return text

        

    def parse(self, font_statistics, toc, pages: Dict[int, List[List[LayoutElement]]]):
        self.fit_font_predictor(font_statistics)
        out = self.parse_page(pages[0])
        print(out)
        return [],[]