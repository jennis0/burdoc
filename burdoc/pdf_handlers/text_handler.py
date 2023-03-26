import logging
from typing import List

import fitz

from ..elements.bbox import Bbox
from ..elements.line import LineElement
from ..utils.logging import get_logger


class TextHandler(object):
    """Extracts text lines from a PDF then applies standardisation and filtering to them
    """

    def __init__(self, pdf: fitz.Document, log_level: int=logging.INFO):
        self.logger = get_logger('text-handler', log_level=log_level)
        self.pdf = pdf

    def _filter_and_clean_lines(self, lines: List[LineElement]) -> List[LineElement]:
        """Apply basic filtering over all lines in a page. Currently:
        - Removes duplicate text with overlapping bounding boxes;
        - Merges lone bullet points into the next piece of text;
        - Merges large letters at the start of paragraphs with the next piece of text.

        Args:
            lines (List[LineElement]): Lines to filter

        Returns:
            List[LineElement]: Filtered lines
        """
        if len(lines) == 1:
            return lines

        skip = [False for _ in range(len(lines))]
        lines.sort(key=lambda l: round(l.bbox.y0/5, 0)*100 + l.bbox.x0)

        for i,line in enumerate(lines):
            if skip[i]:
                continue

            line_text = line.get_text().strip()
            if line_text == "":
                skip[i] = True
                continue
                        
            #Merge text with incorrect character spacing 
            for span in line.spans:
                if len(span.text) > 1 and span.text[1] == " ":
                    if len(span.text) < 4 or span.text[1] == span.text[3]:
                        if len(span.text) < 6 or span.text[1] == span.text[5]:
                            span.text = span.text.replace(" ","")

            #Filter line duplicates
            for j,test_line in enumerate(lines):
                if i == j or skip[j]:
                    continue

                if test_line.bbox.y0 > line.bbox.y0 + 3:
                    break

                test_line_text = test_line.get_text()
                if line_text == test_line_text and test_line.bbox.overlap(line.bbox, 'min') > 0.2:
                    skip[j] = True
            
            #Merge separated bullet points
            if line_text == "\u2022":
                for j, test_line in enumerate(lines):
                    if i == j or skip[j]:
                        continue

                    if test_line.bbox.y_overlap(line.bbox, 'second') > 0.5 and abs(line.bbox.x1 - test_line.bbox.x0) < 20:
                        test_line.spans.insert(0, line.spans[0])
                        test_line.bbox = Bbox.merge([line.bbox, test_line.bbox])
                        skip[i] = True
                        break
                if skip[i]:
                    break
                continue
                        
            #Merge large paragraph starting characters
            if len(line_text) == 1 and line.spans[0].font.size > 15:
                for j,test_line in enumerate(lines):
                    if i == j or skip[j]:
                        continue
                    
                    if test_line.bbox.y_overlap(line.bbox, 'first') > 0.8 and abs(line.bbox.x1 - test_line.bbox.x0) < 25:
                        if line_text == test_line.get_text()[0]:
                            test_line.spans[0].text = test_line.spans[0].text[1:]
                        test_line.spans.insert(0, line.spans[0])
                        test_line.bbox = Bbox.merge([line.bbox, test_line.bbox])
                        skip[i] = True
                        break
                if skip[i]:
                    break

        lines = [line for i,line in enumerate(lines) if not skip[i]]
        
        return lines

    def get_page_text(self, page: fitz.Page) -> List[LineElement]:
        """Returns cleaned, standardised set of LineElements from a PDF page.
        Currently applies:
        - Duplicate detection
        - Bullet Point detection and assignment
        - Large starting character detection and assignment

        Args:
            page (fitz.Page)

        Returns:
            List[LineElement]
        """
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
                    line['spans'][0]['text'] = "\u2022"
                    line['spans'][0]['font'] = "Wingdings-Replaced"

                block_lines.append(
                    LineElement.from_dict(line, bound[2], bound[3])
                )

            lines += self._filter_and_clean_lines(block_lines)

        self.logger.debug("Found %d lines of text", len(lines))
        return lines