import logging
import os
import time
from typing import Any, Dict, List, Tuple

import fitz
import numpy as np
from PIL import Image
from plotly.graph_objects import Figure

from ...elements import (Bbox, DrawingElement, DrawingType, ImageType,
                         LineElement, Span)
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

    def _read_pdf(self, path: str):
        self.logger.debug('Loading %s', path)
        try:
            pdf = fitz.open(path)
        except RuntimeError as error:
            self.logger.exception("Failed to open %s", path, exc_info=error)
            pdf = None

        return pdf

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
                font_statistics[family] = {'_counts': {}}

            if basefont not in font_statistics[family]:
                font_statistics[family][basefont] = dict(
                    family=family, basefont=basefont, counts={}, true_sizes={})

        for t in text:
            for s in t.spans:
                try:    
                    l = 1
                    size = s.font.size
                    if size not in font_statistics[s.font.family][s.font.name]['counts']:
                        font_statistics[s.font.family][s.font.name]['counts'][size] = l
                        if t.rotation[0] == 1.0:
                            font_statistics[s.font.family][s.font.name]['true_sizes'][size] = [s.bbox.height()]
                        else:
                            font_statistics[s.font.family][s.font.name]['true_sizes'][size] = [s.bbox.width()]
                        font_statistics[s.font.family]['_counts'][size] = l
                    else:
                        font_statistics[s.font.family]['_counts'][size] += l
                        font_statistics[s.font.family][s.font.name]['counts'][size] += l
                        if t.rotation[0] == 1.0:
                            font_statistics[s.font.family][s.font.name]['true_sizes'][size].append(s.bbox.height())
                        else:
                            font_statistics[s.font.family][s.font.name]['true_sizes'][size].append(s.bbox.width())
                    font_statistics[s.font.family][s.font.name]['data'] = s.font.to_json()
                except KeyError:
                    if s.font.family not in font_statistics:
                        font_statistics[s.font.family] = {
                            '_counts': {s.font.size: 1}}
                    if s.font.name not in font_statistics[s.font.family]:
                        font_statistics[s.font.family][s.font.name] = dict(
                            family=s.font.family, basefont=s.font.name, counts={s.font.size: 1})

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

        start = time.perf_counter()
        pdf = self._read_pdf(path)
        if not pdf:
            self.logger.error("Failed to load PDF from %s", path)
            return
        performance_tracker['read_pdf'].append(time.perf_counter() - start)

        text_handler = TextHandler(pdf, self.log_level)
        image_handler = ImageHandler(pdf, self.log_level)
        drawing_handler = DrawingHandler(pdf, self.log_level)

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

            # Sometimes choose to ignore images if not needed
            if not self.ignore_images:
                start = time.perf_counter()
                image_elements, images = image_handler.get_image_elements(
                    page, data['page_images'][page_number], page_colour
                )
                performance_tracker['image_handler'].append(
                    time.perf_counter() - start)
            else:
                image_elements = []
                images = []

            data['image_elements'][int(page_number)] = image_elements
            data['images'][int(page_number)] = images

            start = time.perf_counter()
            data['drawing_elements'][page_number] = drawing_handler.get_page_drawings(
                page, page_colour)
            performance_tracker['drawing_handler'].append(
                time.perf_counter() - start)

            start = time.perf_counter()
            data['text_elements'][page_number] = text_handler.get_page_text(
                page)
            performance_tracker['image_handler'].append(
                time.perf_counter() - start)

            if DrawingType.BULLET in data['drawing_elements'][page_number]:
                self.merge_bullets_into_text(
                    data['drawing_elements'][page_number][DrawingType.BULLET], data['text_elements'][page_number])
            self.update_font_statistics(data['metadata']['font_statistics'], page.get_fonts(
            ), data['text_elements'][page_number])

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

                if t.bbox.y_overlap(b.bbox, 'second') > 0.6 and abs(t.bbox.x0 - b.bbox.x1) < 25:
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
            DrawingType.LINE: "DarkBlue",
            DrawingType.RECT: "Blue",
            DrawingType.BULLET: "LightBlue",
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
