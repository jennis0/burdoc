import logging
import fitz
from typing import List, Any
from .layout_objects import LLine

class TextHandler(object):

    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.logger = logger.getChild('texthandler')
        self.pdf = pdf

    def _remove_line_duplicates(self, lines: List[LLine]) -> List[LLine]:
        skip = [False for l in range(len(lines))]
        for i,l1 in enumerate(lines):
            if skip[i]:
                continue
            
            t1 = l1.get_text()
            if t1.strip() == "":
                skip[i] = True
                continue

            if len(lines) > 1:
                for j,l2 in enumerate(lines[i+1:]):
                    if skip[j]:
                        continue
                    t2 = l2.get_text()

                    if t1 == t2 and l2.bbox.overlap(l1.bbox, 'min') > 0.2:
                        skip[i+j] = True
        lines = [l for i,l in enumerate(lines) if not skip[i]]
        return lines

    def _clean_text(self, lines: List[LLine]) -> List[LLine]:
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
        self.logger.debug("Starting text extraction")
        textpage = page.get_textpage(flags=fitz.TEXTFLAGS_DICT & fitz.TEXT_DEHYPHENATE & ~fitz.TEXT_PRESERVE_LIGATURES )
        data = textpage.extractDICT()
        bound = page.bound()

        lines = []
        for block in data['blocks']:
            block_lines = []
            for line in block['lines']:
                block_lines.append(
                    LLine.from_dict(line, bound[2], bound[3])
                )
            lines += self._remove_line_duplicates(block_lines)

        lines = self._clean_text(lines)
        self.logger.debug(f"Found {len(lines)} lines of text")
        return lines