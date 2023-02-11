from collections import namedtuple
from PIL import Image
import logging
import fitz
import os
from typing import Any, List, Dict

from .drawing_handler import DrawingHandler
from .image_handler import ImageHandler
from .text_handler import TextHandler
from .content_parser import ContentParser
from .layout_builder import LayoutBuilder
from .layout_objects import LLine

ParsedPDF = namedtuple('ParsedPDF', ['title', 'metadata', 'fonts', 'pages', 'page_images'])
    

class PDFReader(object):

    def __init__(self, logger: logging.Logger = None):
        if not logger:
            logger = logging.getLogger()
        self.logger = logger.getChild('pdfreader')
        self.pdf = None
        self.textHandler = None
        self.imageHandler = None
        self.drawingHandler = None
        self.layoutBuilder = None

    def _read_pdf(self, path:os.PathLike):
        self.logger.debug(f'Loading {path}')
        try:
            self.pdf = fitz.open(path)
        except Exception as e:
            self.logger.exception(f"Failed to open {path}", exc_info=e)
            self.pdf = None
        
        return self.pdf

    def _load_handlers(self, pdf: fitz.Document):
        self.textHandler = TextHandler(self.logger, pdf)
        self.imageHandler = ImageHandler(self.logger, pdf)
        self.drawingHandler = DrawingHandler(self.logger, pdf)
        self.layoutBuilder = LayoutBuilder(self.logger, pdf)
        self.contentParser = ContentParser(self.logger)


    def get_page_image(self, page: fitz.Page) -> Image:
        pix = page.get_pixmap()

        return Image.frombytes('RGB', [pix.width, pix.height], pix.samples)


    def update_font_statistics(self, font_statistics: Dict[str, Any], fonts: List[Any], text: List[LLine]):
        for f in fonts:
            if "+" in f[3]:
                basefont = f[3].split("+")[1]
            else:
                basefont = f[3]

            family = basefont.split("-")[0].split("_")[0]
            if family == '':
                family = 'Unnamed'
                basefont = f'Unnamed-T{f[2][-1]}'
            if family not in font_statistics:
                font_statistics[family] = {'_counts':{}}

            if basefont not in font_statistics[family]:
                font_statistics[family][basefont] =  dict(id=f[0], ext=f[1], type=f[2], family=family, basefont=basefont, encoding=f[5], counts={})

        for t in text:
            for s in t.spans:
                try:
                    l = 1
                    size = s.font.size
                    if size not in font_statistics[s.font.family][s.font.name]['counts']:
                        font_statistics[s.font.family][s.font.name]['counts'][size] = l
                        font_statistics[s.font.family]['_counts'][size] = l
                    else:
                        font_statistics[s.font.family]['_counts'][size] += l
                        font_statistics[s.font.family][s.font.name]['counts'][size] += l
                except:
                    print(s.font)


    def read(self, path: os.PathLike, page_start: int=0, page_stop: int=None, step=1) -> ParsedPDF:
        
        doc = self._read_pdf(path)
        if not doc:
            return None
        
        self._load_handlers(doc)

        if page_start > 0:
            if page_stop:
                page_gen = doc.pages(start=page_start, stop=page_stop, step=1)
            else:
                page_gen = doc.pages(start=page_start, stop=None, step=1)
        elif page_stop:
            page_gen = doc.pages(start=0, stop=page_stop)
        else:
            page_gen = doc.pages(0, None, step=step)        

        title = os.path.basename(path)
        metadata = doc.metadata
        font_stats = {}
        pages = {}
        content = {}
        page_images = {}
        images = {}

        for i,page in enumerate(page_gen):
            page_number = page_start + step*i
            self.logger.debug(f"Reading page {page_number}")

            page_images[page_number] = self.get_page_image(page)
            images[page_number] = self.imageHandler.get_page_images(page)
            drawings = self.drawingHandler.get_page_drawings(page)

            text = self.textHandler.get_page_text(page)
            self.update_font_statistics(font_stats, page.get_fonts(), text)

            pages[page_number] = self.layoutBuilder.compute_layout(page, text, images[page_number], drawings, page_images[page_number])

        content, toc = self.contentParser.parse(font_stats, self.pdf.get_toc(), pages)

        results = {
            'title':title,
            'metadata':metadata,
            'toc':toc,
            'content':content,
            'layout':pages
        }

        return results