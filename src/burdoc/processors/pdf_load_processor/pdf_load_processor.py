import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import fitz
import numpy as np
from PIL import Image
from plotly.graph_objects import Figure

from ...elements import (Bbox, DrawingElement, DrawingType, ImageElement,
                         ImageType, LineElement, Span, Font)
from ...utils.image_manip import get_image_palette
from ...utils.render_pages import add_rect_to_figure
from ..processor import Processor
from .drawing_handler import DrawingHandler
from .image_handler import ImageHandler
from .text_handler import TextHandler


class PDFLoadProcessor(Processor):
    """Loads PDF from file and extracts essential information 
    with minor processing/cleaning applied

    ::

        Requires: None
        Generates: ['page_bounds', 'text_elements', 'image_elements', 'drawing_elements', 'images', 'page_images']

    """

    name: str = 'pdf-load'
    threadable = True

    def __init__(self, log_level: int = logging.INFO, ignore_images: bool = False):
        """Creates a PDF Load Processor

        Args:
            log_level (int, optional): Log level. Defaults to logging.INFO.
            ignore_images (bool, optional): Ignore images. This will greatly increase
                the speed but will likely cause issues if images are used for layout
                purposes, such as as section background or section breaks. Defaults to False.
        """
        super().__init__(PDFLoadProcessor.name, log_level=log_level)

        self.log_level = log_level
        self.ignore_images = ignore_images

    def requirements(self) -> Tuple[List[str], List[str]]:
        return ([], [])

    def generates(self) -> List[str]:
        return ['page_bounds', 'text_elements', 'image_elements',
                'page_images', 'drawing_elements', 'images']

    def get_page_image(self, page: fitz.Page) -> Image.Image:
        pix = page.get_pixmap()
        return Image.frombytes('RGB', [pix.width, pix.height], pix.samples)

    def _update_font_statistics(self, font_statistics: Dict[str, Any], fonts: List[Any], text: List[LineElement]):
        
        for font in fonts:
            family, basefont = Font.split_font_name(font[3], font[2])
            
            if family not in font_statistics:
                font_statistics[family] = {'_counts': {}}

            if basefont not in font_statistics[family]:
                font_statistics[family][basefont] = {'family': family,
                                                     'basefont': basefont,
                                                     'counts': {},
                                                     'true_sizes': {}}

        for line in text:
            for span in line.spans:
                
                weight = len(span.text)
                size = span.font.size
                
                if span.font.family not in font_statistics:
                    font_statistics[span.font.family] = {
                        '_counts': {}
                    }
                    fs_fam = font_statistics[span.font.family]
                else:
                    fs_fam = font_statistics[span.font.family]
                                    
                if size not in fs_fam['_counts']:
                    fs_fam['_counts'][size] = 0
                
                fs_fam['_counts'][size] += weight
                    
                if span.font.name not in fs_fam:
                    fs_fam[span.font.name] = {
                            'family': span.font.family,
                            'basefont': span.font.name,
                            'counts': {},
                            'true_sizes': {}
                        }
                    fs_name = fs_fam[span.font.name]
                else:
                    fs_name = fs_fam[span.font.name]

                
                if size not in fs_name['counts']:
                    fs_name['counts'][size] = weight
                    fs_name['true_sizes'][size] = []
                else:
                    fs_name['counts'][size] += weight
                    
                if line.rotation[0] == 1.0:
                    fs_name['true_sizes'][size].append(span.bbox.height())
                else:
                    fs_name['true_sizes'][size].append(span.bbox.width())
                
                font_statistics[span.font.family][span.font.name]['data'] = span.font.to_json()


    def _add_metadata_and_fields(self, data: Dict[str, Any], path: str, pdf: fitz.Document) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            'title': os.path.basename(path),
            'pdf_metadata': pdf.metadata,
            'font_statistics': {},
            'toc': pdf.get_toc()
        }

        new_fields: Dict[str, Dict[int, Any]] = {
            'page_bounds': {},
            'image_elements': {},
            'images': {},
            'page_images': {},
            'text_elements': {},
            'drawing_elements': {},
        }
        data['metadata'] |= metadata
        data |= new_fields
        return data

    def _get_drawings(self,
                      drawing_handler: DrawingHandler,
                      page: fitz.Page,
                      page_colour: Any,
                      performance_tracker: Dict[str, List[float]]) -> Dict[DrawingType, List[DrawingElement]]:
        start = time.perf_counter()
        result = drawing_handler.get_page_drawings(page, page_colour)
        performance_tracker['drawing_handler'].append(time.perf_counter() - start)
        return result

    def _get_text(self,
                  text_handler: TextHandler,
                  page: fitz.Page,
                  performance_tracker: Dict[str, List[float]]) -> List[LineElement]:
        start = time.perf_counter()
        result = text_handler.get_page_text(page)
        performance_tracker['text_handler'].append(time.perf_counter() - start)
        return result

    def _get_images(self,
                    image_handler: ImageHandler,
                    page: fitz.Page,
                    page_colour,
                    page_image: Image.Image,
                    performance_tracker
                    ) -> Tuple[Dict[ImageType, List[ImageElement]], List[Image.Image]]:

        if not self.ignore_images:
            start = time.perf_counter()
            image_elements, images = image_handler.get_image_elements(
                page, page_image, page_colour
            )
            performance_tracker['image_handler'].append(
                time.perf_counter() - start)
        else:
            image_elements = []
            images = []

        return image_elements, images

    def _read_pdf(self,
                  path: str,
                  performance_tracker: Dict[str, List[float]]) -> Optional[fitz.Document]:
        start = time.perf_counter()

        self.logger.debug('Loading %s', path)

        try:
            pdf = fitz.open(path)
        except RuntimeError as error:
            self.logger.exception("Failed to open %s", path, exc_info=error)
            pdf = None

        performance_tracker['read_pdf'].append(time.perf_counter() - start)
        return pdf

    def _process(self, data: Dict[str, Any]):

        performance_tracker: Dict[str, List[float]] = {
            'read_pdf': [],
            'load_page': [],
            'page_image_generation': [],
            'image_handler': [],
            'drawing_handler': [],
            'text_handler': []
        }

        path = data['metadata']['path']
        pages = data['slice']
        self.logger.debug("Loading path %s", path)
        self.logger.debug("Loading pages %s", pages)

        pdf = self._read_pdf(path, performance_tracker)
        if not pdf:
            return None

        text_handler = TextHandler(pdf, self.log_level)
        image_handler = ImageHandler(pdf, self.log_level)
        drawing_handler = DrawingHandler(pdf, self.log_level)

        self._add_metadata_and_fields(data, path, pdf)

        page_count = pdf.page_count

        for page_number in pages:
            page_number = int(page_number)
            if page_number >= page_count:
                self.logger.warning(
                    "Skipping page %d as only %d pages", page_number+1, page_count)
                continue
            self.logger.debug("Reading page %d", page_number)
            start = time.perf_counter()
            page = pdf.load_page(int(page_number))
            performance_tracker['load_page'].append(
                time.perf_counter() - start)
            self.logger.debug("Page loaded")

            bound = page.bound()
            data['page_bounds'][page_number] = Bbox(
                *bound, bound[2], bound[3])  # type:ignore

            start = time.perf_counter()
            data['page_images'][page_number] = self.get_page_image(page)
            performance_tracker['page_image_generation'].append(
                time.perf_counter() - start)

            page_colour = np.array(get_image_palette(
                data['page_images'][page_number], n_colours=1)[0][0])

            image_elements, images = self._get_images(image_handler, page,
                                                      page_colour, data['page_images'][page_number],
                                                      performance_tracker)

            data['image_elements'][int(page_number)] = image_elements
            data['images'][int(page_number)] = images

            data['drawing_elements'][page_number] = self._get_drawings(drawing_handler, page,
                                                                       page_colour, performance_tracker)

            data['text_elements'][page_number] = self._get_text(text_handler, page, performance_tracker)

            if DrawingType.BULLET in data['drawing_elements'][page_number]:
                self.merge_bullets_into_text(
                    data['drawing_elements'][page_number][DrawingType.BULLET], data['text_elements'][page_number])
            
            self._update_font_statistics(data['metadata']['font_statistics'], page.get_fonts(), data['text_elements'][page_number])

        pdf.close()

        for k, values in performance_tracker.items():
            data['performance'][self.name][k] = [round(sum(values), 3)]

    def merge_bullets_into_text(self, bullets: List[DrawingElement], text: List[LineElement]):
        """Merge lone bullet points found as drawings into their closest text lines.

        Args:
            bullets (List[DrawingElement])
            text (List[LineElement])
        """
        if len(bullets) == 0:
            return

        b_used = [False for _ in bullets]
        for t in text:
            for i, b in enumerate(bullets):
                if b_used[i]:
                    continue

                distance = 25 if b.bbox.width() > 8 else 10
                
                if b.bbox.height() / t.bbox.height() > 0.7:
                    continue

                if t.bbox.y_overlap(b.bbox, 'second') > 0.6 and abs(t.bbox.x0 - b.bbox.x1) < distance:
                    t.spans.insert(0, Span(b.bbox, font=t.spans[0].font, text="\u2022 "))
                    t.bbox = Bbox.merge([t.bbox, b.bbox])
                    b_used[i] = True
                    break
            if all(b_used):
                break

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):

        colours = {
            ImageType.PRIMARY: "DarkRed",
            ImageType.BACKGROUND: "Red",
            ImageType.SECTION: "Pink",
            DrawingType.LINE: "Green",
            DrawingType.RECT: "Blue",
            DrawingType.BULLET: "LightBlue",
            DrawingType.TABLE: "Yellow",
            "text_elements": "Grey",
        }

        for e in data['text_elements'][page_number]:
            add_rect_to_figure(fig, e.bbox, colours['text_elements'])
        fig.add_scatter(x=[None], y=[None], name="Line", line=dict(
            width=3, color=colours['text_elements']))

        for im_type in data['images'][page_number]:
            if im_type in colours:
                colour = colours[im_type]
                for im in data['images'][page_number][im_type]:
                    add_rect_to_figure(fig, im.bbox, colour)
                fig.add_scatter(x=[None], y=[None], name=f"{im_type.name}", line=dict(
                    width=3, color=colour))

        for dr_type in data['drawing_elements'][page_number]:
            if dr_type in colours:
                colour = colours[dr_type]
                for dr in data['drawing_elements'][page_number][dr_type]:
                    add_rect_to_figure(fig, dr.bbox, colour)
                fig.add_scatter(x=[None], y=[None], name=f"{dr_type.name}", line=dict(
                    width=3, color=colour))
