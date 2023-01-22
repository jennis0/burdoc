from enum import Enum, auto
from PIL import Image as PILImage
import fitz
import numpy as np
import logging
import io
from typing import List
from .bbox import Bbox
from .layout_objects import Image

class ImageHandler(object):



    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.cache = {}
        self.page_bbox = None
        self.logger = logger.getChild('imagehandler')
        self.pdf = pdf

    def _get_image(self, xref: str) -> Image:
        image = self.pdf.extract_image(xref)
        if image:
            pil_image = PILImage.open(io.BytesIO(image['image']))
            return pil_image
        return None

    def _classify_image(self, imageData: Image) -> Image.ImageType:
    
        #Calculate visible area of image intersected with visible area of page
        x_coverage = round(imageData.bbox.x_overlap(self.page_bbox, 'second'), 3)
        y_coverage = round(imageData.bbox.y_overlap(self.page_bbox, 'second'), 3)
        page_coverage =  x_coverage * y_coverage

        image = np.asarray(imageData.image)
        x_variance = round(np.median(image.var(axis=0), axis=0).mean(), 2)
        y_variance = round(np.median(image.var(axis=1), axis=0).mean(), 2)

        extrema = imageData.image.getextrema()
        if len(extrema) == 2:
            extrema = [extrema]
        maxExtrema = max([b-a for a,b in extrema])
        
        #print(var, x_coverage, y_coverage, page_coverage)
        imageData.properties['variance'] = {'x':x_variance, 'y':y_variance}
        imageData.properties['coverage'] = {'x':x_coverage, 'y':y_coverage, 'page':page_coverage}
        imageData.properties['extrema'] = maxExtrema

        #If cover is too small, we can't see it
        if page_coverage <= 0.001:
            return Image.ImageType.Invisible

        #If thin in one dimension, treat as line rather than image
        if (x_coverage < 0.05 and y_coverage > 0.1) or (x_coverage > 0.1 and y_coverage < 0.05):
            return Image.ImageType.Line

        #If it's too small in any particular dimension it can't be a meaningful image
        if x_coverage < 0.05 or y_coverage < 0.05 or page_coverage < 0.05:
            return Image.ImageType.Decorative

        #If complexity is low it could be either a full page background or a section
        if x_variance < 50 and y_variance < 50 and maxExtrema < 50:
            if page_coverage > 0.9:
                return Image.ImageType.Background
            elif page_coverage > 0.1:
                return Image.ImageType.Section
            else:
                return Image.ImageType.Decorative

        if (x_variance < 50 and y_variance > 1000) or (x_variance > 1000 and y_variance < 50):
            return Image.ImageType.Gradient

        if page_coverage < 0.05 or x_coverage < 0.15 or y_coverage < 0.15:
            return Image.ImageType.Decorative

        return Image.ImageType.Primary

                    
    def get_page_images(self, page: fitz.Page) -> List[Image]:
        self.logger.debug("Starting image extraction")
        
        self.page_bbox = Bbox(*page.bound())
        images = page.get_image_info(hashes=False, xrefs=True)
        processed_images = {t.name:[] for t in Image.ImageType}

        for i in images:
            image = self._get_image(i['xref'])
            if image:
                im = Image(None, Bbox(*i['bbox']), image, {})
                im.type = self._classify_image(im)
                processed_images[im.type.name].append(im)

        for t in processed_images:
            self.logger.debug(f"Found {len(processed_images[t])} {t} images")
        return processed_images