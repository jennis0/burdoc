from collections import namedtuple
from PIL import Image
import logging
import fitz
import os

from .drawing_handler import DrawingHandler
from .image_handler import ImageHandler
from .text_handler import TextHandler
from .layout_builder import LayoutBuilder

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


    def get_page_image(self, page: fitz.Page) -> Image:
        pix = page.get_pixmap()

        return Image.frombytes('RGB', [pix.width, pix.height], pix.samples)


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
        fonts = {}
        pages = {}
        page_images = {}
        images = {}

        for i,page in enumerate(page_gen):
            print(page)
            page_number = page_start + step*i

            page_images[page_number] = self.get_page_image(page)

            text = self.textHandler.get_page_text(page)
            images[page_number] = self.imageHandler.get_page_images(page)
            drawings = self.drawingHandler.get_page_drawings(page)
            fonts[page_number] = page.get_fonts()

            pages[page_number] = self.layoutBuilder.compute_layout(page, text, images[page_number], drawings, page_images[page_number])

        return ParsedPDF(title, metadata, fonts, pages, page_images)