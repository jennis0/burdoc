import logging
from typing import List, Optional

import fitz

from ..elements.bbox import Bbox
from ..elements.layout_objects import LineElement
from ..utils.logging import get_logger


class TextHandler(object):

    def __init__(self, pdf: fitz.Document, log_level: Optional[int]=logging.INFO):
        self.logger = get_logger('text-handler', log_level=log_level)
        self.pdf = pdf

    def _remove_line_duplicates(self, lines: List[LineElement]) -> List[LineElement]:
        if len(lines) == 1:
            return lines

        skip = [False for l in range(len(lines))]
        lines.sort(key=lambda l: round(l.bbox.y0/5, 0)*100 + l.bbox.x0)

        for i,l1 in enumerate(lines):
            if skip[i]:
                continue

            t1 = l1.get_text().strip()
            if t1 == "":
                skip[i] = True
                continue

            for j,l2 in enumerate(lines[i+1:]):
                if skip[j]:
                    continue

                if l2.bbox.y0 > l1.bbox.y0 + 3:
                    break

                t2 = l2.get_text()

                if t1 == t2 and l2.bbox.overlap(l1.bbox, 'min') > 0.2:
                    skip[i+j] = True
            
            #Merge separated bullet points
            if t1 == u"\u2022" and len(lines) > i+1:
                j = 1
                l2 = lines[i+1]
                while skip[i+j] is True:
                    j += 1
                    if len(lines) <= i+j:
                        break
                    l2 = lines[i+j]
                if l2:
                    if l2.bbox.y_overlap(l1.bbox, 'second') > 0.5 and abs(l1.bbox.x1 - l2.bbox.x0) < 20:
                        l2.spans.insert(0, l1.spans[0])
                        l2.bbox = Bbox.merge([l1.bbox, l2.bbox])
                        skip[i] = True

        lines = [l for i,l in enumerate(lines) if not skip[i]]
        return lines

    def _clean_text(self, lines: List[LineElement]) -> List[LineElement]:
        #Remove lines that contain no text
        lines = [l for l in lines if len(l.get_text().strip()) > 0]
        
        #Clean some text which has erroneous spaces between characters
        #This is common in some headers
        for l in lines:
            for s in l.spans:
                if len(s.text) > 1 and s.text[1] == " ":
                    if len(s.text) < 4 or s.text[1] == s.text[3]:
                        if len(s.text) < 6 or s.text[1] == s.text[5]:
                            s.text = s.text.replace(" ","")

        #Fuse together lines where the first letter is oversized
        for l in lines:
            if len(l.spans) > 2 and l.spans[0].font.size > l.spans[1].font.size:
                if len(l.spans[0].text) == 1:
                    l.spans[0].text += l.spans[1].text
                    l.spans.remove(l.spans[1])

        return lines

    def get_page_text(self, page: fitz.Page):
        fitz.TOOLS.set_small_glyph_heights(True)
        self.logger.debug("Starting text extraction")
        textpage = page.get_textpage(flags=fitz.TEXTFLAGS_DICT & fitz.TEXT_DEHYPHENATE & ~fitz.TEXT_PRESERVE_LIGATURES)
        data = textpage.extractDICT()
        bound = page.bound()

        lines = []
        for block in data['blocks']:
            block_lines = []
            for line in block['lines']:

                if len(line['spans']) == 1 and line['spans'][0]['font'] == 'Wingdings' and len(line['spans'][0]['text']) == 1:
                    line['spans'][0]['text'] = u"\u2022"
                    line['spans'][0]['font'] = "Wingdings-Replaced"

                block_lines.append(
                    LineElement.from_dict(line, bound[2], bound[3])
                )

            lines += self._remove_line_duplicates(block_lines)

        lines = self._clean_text(lines)
        self.logger.debug(f"Found {len(lines)} lines of text")
        return lines