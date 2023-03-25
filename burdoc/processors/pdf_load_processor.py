from PIL import Image
import logging
import fitz
import os
from typing import Any, List, Dict, Optional
from plotly.graph_objects import Figure

from ..pdf_handlers.drawing_handler import DrawingHandler
from ..pdf_handlers.image_handler import ImageHandler
from ..pdf_handlers.text_handler import TextHandler

from ..elements.layout_objects import LineElement, DrawingElement, ImageElement

from ..elements.span import Span

from .processor import Processor
from ..elements.bbox import Bbox
    

class PDFLoadProcessor(Processor):

    def __init__(self, log_level: Optional[int]=logging.INFO):
        super().__init__("pdf-load", log_level=log_level)
        self.log_level = log_level

    def initialise(self):
        return super().initialise()

    def requirements(self) -> List[str]:
        return []
    
    def generates(self) -> List[str]:
        return ['page_bounds', 'text', 'images', 
                'page_images', 'drawings', 'image_store']

    def _read_pdf(self, path:os.PathLike):
        self.logger.debug(f'Loading {path}')
        try:
            pdf = fitz.open(path)
        except Exception as e:
            self.logger.exception(f"Failed to open {path}", exc_info=e)
            pdf = None
        
        return pdf

    def _load_handlers(self, pdf: fitz.Document):
        self.textHandler = TextHandler(pdf, self.log_level)
        self.imageHandler = ImageHandler(pdf, self.log_level)
        self.drawingHandler = DrawingHandler(pdf, self.log_level)

    def get_page_image(self, page: fitz.Page) -> Image:
        pix = page.get_pixmap()
        return Image.frombytes('RGB', [pix.width, pix.height], pix.samples)

    def update_font_statistics(self, font_statistics: Dict[str, Any], fonts: List[Any], text: List[LineElement]):
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
                font_statistics[family][basefont] =  dict(family=family, basefont=basefont, counts={})

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
                    if s.font.family not in font_statistics:
                        font_statistics[s.font.family] = {'_counts':{s.font.size: 1}}
                    if s.font.name not in font_statistics[s.font.family]:
                        font_statistics[s.font.family][s.font.name] = dict(family=s.font.family, basefont=s.font.name, counts={s.font.size: 1})

    def process(self, data: Dict[str, Any]):
        
        path = data['metadata']['path']
        slice = data['slice']
        self.logger.debug(f"Loading path {path}")
        self.logger.debug(f"Loading slice {slice}")

        pdf = self._read_pdf(path)
        if not pdf:
            self.logger.error(f"Failed to load PDF from {path}")
            return None
        self._load_handlers(pdf)
        
        metadata = {
            'title':os.path.basename(path),
            'pdf_metadata':pdf.metadata,
            'font_statistics': {},
            'toc':pdf.get_toc()
        }

        new_fields = {
            'page_bounds': {},
            'images':{},
            'image_store':{},
            'page_images':{},
            'text':{},
            'drawings':{},
        }
        data['metadata'] |= metadata
        data |= new_fields

        page_count = pdf.page_count

        for page_number in slice:
            page_number = int(page_number)
            if page_number >= page_count:
                self.logger.info(f"Skipping page {page_number + 1} as only {page_count} pages")
                continue
            self.logger.debug(f"Reading page {page_number}")
            page = pdf.load_page(int(page_number))
            self.logger.debug("Page loaded")
            
            bound = page.bound()
            data['page_bounds'][page_number] = Bbox(*bound, bound[2], bound[3])
            data['page_images'][page_number] = self.get_page_image(page)
            images, image_store = self.imageHandler.get_page_images(page, data['page_images'][page_number])
            data['images'][int(page_number)] = images
            data['image_store'][int(page_number)] = image_store
            data['drawings'][page_number] = self.drawingHandler.get_page_drawings(page)
            data['text'][page_number] = self.textHandler.get_page_text(page)

            if DrawingElement.DrawingType.Bullet in data['drawings'][page_number]:
                self.merge_bullets_into_text(data['drawings'][page_number][DrawingElement.DrawingType.Bullet], data['text'][page_number])
            self.update_font_statistics(data['metadata']['font_statistics'], page.get_fonts(), data['text'][page_number])

        pdf.close()

    def merge_bullets_into_text(self, bullets: List[DrawingElement], text: List[LineElement]):
        if len(bullets) == 0:
            return
        
        b_used = [False for _ in bullets]
        for t in text:
            for i,b in enumerate(bullets):
                if b_used[i]:
                    continue

                if t.bbox.y_overlap(b.bbox, 'second') > 0.6 and abs(t.bbox.x0 - b.bbox.x1) < 25:
                    t.spans.insert(0, Span(t.spans[0].font, u"\u2022"))
                    t.bbox = Bbox.merge([t.bbox, b.bbox])
                    b_used[i] = True
                    break
            if all(b_used):
                break

    def add_generated_items_to_fig(self, page_number:int, fig: Figure, data: Dict[str, Any]):

        colours = {
            ImageElement.ImageType.Primary:"DarkRed",
            ImageElement.ImageType.Background:"Red",
            ImageElement.ImageType.Section:"Pink",
            DrawingElement.DrawingType.Line:"DarkBlue",
            DrawingElement.DrawingType.Rect:"Blue",
            DrawingElement.DrawingType.Bullet:"LightBlue",
            "text":"Grey",
        }

        def add_rect(fig, bbox, colour):
            fig.add_shape(
                type='rect', xref='x', yref='y', opacity=0.6,
                x0 = bbox.x0, y0=bbox.y0, x1 = bbox.x1, y1 = bbox.y1,
                line=dict(color=colour, width=3)
            )

        for e in data['text'][page_number]:
            add_rect(fig, e.bbox, colours['text'])
        fig.add_scatter(x=[None], y=[None], name="Line", line=dict(width=3, color=colours['text']))

        for im_type in data['images'][page_number]:
            if im_type in colours:
                colour = colours[im_type]
                for im in data['images'][page_number][im_type]:
                    add_rect(fig, im.bbox, colour)
                fig.add_scatter(x=[None], y=[None], name=f"{im_type.name}", line=dict(width=3, color=colour))

        for dr_type in data['drawings'][page_number]:
            if dr_type in colours:
                colour = colours[dr_type]
                for dr in data['drawings'][page_number][dr_type]:
                    add_rect(fig, dr.bbox, colour)
                fig.add_scatter(x=[None], y=[None], name=f"{dr_type.name}", line=dict(width=3, color=colour))