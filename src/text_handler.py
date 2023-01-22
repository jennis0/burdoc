import logging
import fitz
from typing import List, Any
from .layout_objects import Line

class TextHandler(object):

    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.logger = logger.getChild('texthandler')
        self.pdf = pdf

    def _remove_line_duplicates(self, blocks: List[Any]) -> List[Any]:
        for block in blocks:
            skip = [False for l in range(len(block['lines']))]
            if len(block['lines']) > 1:
                for i,l1 in enumerate(block['lines'][:-1]):
                    if skip[i]:
                        continue
                    l2 = block['lines'][i+1]
                    t1 = "".join([s['text'] for s in l1['spans']])
                    t2 = "".join([s['text'] for s in l2['spans']])

                    if t1.strip() == "":
                        skip[i] = True
                        continue

                    if t1 == t2 and abs(l1['bbox'][1] - l2['bbox'][1]) < 0.005 \
                            and abs(l1['bbox'][0] - l2['bbox'][0]) < 0.05:
                        skip[i+1] = True
            block['lines'] = [l for i,l in enumerate(block['lines']) if not skip[i]]
        return blocks

    def get_page_text(self, page: fitz.Page):
        self.logger.debug("Starting text extraction")
        textpage = page.get_textpage(flags=fitz.TEXTFLAGS_DICT & fitz.TEXT_DEHYPHENATE & ~fitz.TEXT_PRESERVE_LIGATURES )
        data = textpage.extractDICT()
        blocks = self._remove_line_duplicates(data['blocks'])

        lines = []
        for block in blocks:
            for line in block['lines']:
                lines.append(
                    Line.from_dict(line)
                )
        
        self.logger.debug(f"Found {len(lines)} lines of text")
        return lines