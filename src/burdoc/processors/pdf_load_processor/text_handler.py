import logging
import re
from typing import List

import fitz

from ...elements import Bbox, LineElement, Span
from ...utils.logging import get_logger
from ...utils.regexes import get_list_regex


class TextHandler():
    """Extracts text lines from a PDF then applies standardisation and filtering to them
    """

    def __init__(self, pdf: fitz.Document, log_level: int = logging.INFO):
        self.logger = get_logger('text-handler', log_level=log_level)
        self.pdf = pdf
        self.list_regex = get_list_regex()
        self.dubious_space_regex = re.compile("([a-zA-Z0-9]{1,2}\\s){3,}", re.UNICODE)
        self.compare_window = 4
        self.bullet_merge_distance = 20


    def _are_duplicates(self, line1: LineElement, line2: LineElement) -> int:
        """Compares two line elements and evaluates if they are duplicates.

        Note that duplicates includes substring duplicates where only part of the longer
        line is duplicated as this is sometime used for emphasis.


        Returns 1 if the 1st line should be removed and 2 if the 2nd line should be
        removed.

        Args:
            line1 (LineElement): A line element
            line2 (LineElement): A line element

        Returns:
            int: 0 if not duplicates, 2 if line2 is a duplicate/substring duplicate of line1
                1 if line1 is a duplicate/substring duplicate of line2
        """
        text1 = line1.get_text().strip()
        text2 = line2.get_text().strip()
    
        if len(text1) > len(text2):
            shorter = text2
            longer = text1
            result = 2
        else:
            shorter = text1
            longer = text2
            result = 1

        if line1.bbox.overlap(line2.bbox, 'min') > 0.5 and shorter in longer:
            return result

        return 0


    def _remove_dubious_spaces(self, line: LineElement):
        """MuPDF will sometimes add additional spaces in heading text with decorative fonts.
        Try to identify this and remove

        Args:
            line (LineElement): Line element to modify
        """
        # Doesn't seem to happen with small text
        if line.spans[0].font.size < 13:
            return

        if self.dubious_space_regex.match(line.get_text()):
            for span in line.spans:
                span.text = span.text.replace("  ", "^_^_")
                span.text = span.text.replace(" ", "")
                span.text = span.text.replace("^_^_", " ")


    def _try_merge_separated_bullets(self, line1: LineElement, line2: LineElement) -> bool:
        """Tests whether the first line (which should already have been determined to be a bullet point)
        actually belongs at the start of the second line. If found, performs the merge

        Args:
            line1 (LineElement): A bullet point
            line2 (LineElement): A line of text

        Returns:
            bool: True if line1 has been merged into line 2
        """
        has_y_overlap = line1.bbox.y_overlap(line2.bbox, 'first') > 0.5
        close_in_x = (line2.bbox.x0 - line1.bbox.x1) < self.bullet_merge_distance and \
            (line2.bbox.x0 - line1.bbox.x1) > -5

        if has_y_overlap and close_in_x and line2.get_text() != line1.get_text():
            line1.spans[0].text += "\t"
            new_spans = [line1.spans[0],
                         Span(bbox=Bbox(line1.bbox.x1, line1.bbox.y0,
                                        line2.bbox.x0, line1.bbox.y1,
                                        line1.bbox.page_width,
                                        line1.bbox.page_height),
                              font=line1.spans[0].font, text="\t")]
            line2.spans = new_spans + line2.spans
            line2.bbox = Bbox.merge(
                [s.bbox for s in line2.spans])

            return True
        return False

    def _try_merge_large_first_letters(self, line1: LineElement, line2: LineElement) -> bool:
        """Tests whether the first line is a large, decorative single letter. Uses the fact that
        (good) PDFs usually leave the true first letter in the line before to aid screenreaders.

        Args:
            line1 (LineElement): A potential first letter
            line2 (LineElement): A potential sentence to merge

        Returns:
            bool: True if 1st line was merged with 2nd
        """

        if line2.bbox.y_overlap(line1.bbox, 'first') > 0.8 and abs(line1.bbox.x1 - line2.bbox.x0) < 25:
            if line1.get_text().strip() == line2.get_text()[0]:
                line2.spans[0].text = line2.spans[0].text[1:]
            line2.spans.insert(0, line1.spans[0])
            line2.bbox = Bbox.merge(
                [line1.bbox, line2.bbox])
            return True

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
        lines.sort(key=lambda l: round(l.bbox.y0, 0)*1000 + l.bbox.x0)

        for i, line in enumerate(lines):
                        
            if skip[i]:
                continue

            line_text = line.get_text().strip()
            if line_text == "":
                skip[i] = True
                continue

            # Merge text with incorrect character spacing
            self._remove_dubious_spaces(line)

            near_line_offset = max(0, i-self.compare_window)
            near_lines = lines[near_line_offset:i+self.compare_window]

            # Filter line duplicates
            for j, test_line in enumerate(near_lines):
                true_j = j + near_line_offset
                if i == true_j or skip[true_j]:
                    continue
                
                if test_line.bbox.y0 > line.bbox.y0 + 3:
                    break

                are_duplicates = self._are_duplicates(line, test_line)
                if are_duplicates == 1:
                    skip[i] = True
                    break
                elif are_duplicates == 2:
                    skip[true_j] = True

            # Merge separated bullet points
            list_match = self.list_regex.match(line_text)
            if list_match and list_match.end() == len(line_text):
                for j, test_line in enumerate(near_lines):
                    true_j = j + near_line_offset
                    if i == true_j or skip[true_j]:
                        continue

                    if test_line.bbox.y0 > line.bbox.y1:
                        break

                    did_merge = self._try_merge_separated_bullets(line, test_line)
                    if did_merge:
                        skip[i] = True
                        break
                continue

            # Merge large paragraph starting characters
            if len(line_text) == 1 and line.spans[0].font.size > 15:
                for j, test_line in enumerate(near_lines):
                    true_j = j + near_line_offset
                    if i == true_j or skip[true_j]:
                        continue

                    did_merge = self._try_merge_large_first_letters(line, test_line)
                    if did_merge:
                        skip[i] = True
                        break

        lines = [line for i, line in enumerate(lines) if not skip[i]]

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
        textpage = page.get_textpage(
            flags=fitz.TEXTFLAGS_DICT &
            fitz.TEXT_DEHYPHENATE &
            ~fitz.TEXT_PRESERVE_LIGATURES
        )
        data = textpage.extractDICT()
        bound = page.bound()

        data['blocks'].sort(key=lambda b: b['bbox'][1])

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

            lines += block_lines

        lines = self._filter_and_clean_lines(lines)

        self.logger.debug("Found %d lines of text", len(lines))
        return lines
