from enum import Enum, auto
from PIL import Image as PILImage
import PIL.ImageOps
import fitz
import numpy as np
import logging
import io
from typing import List, Tuple
from .bbox import Bbox
from .layout_objects import LImage

import plotly.express as plt

class ImageHandler(object):



    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.cache = {}
        self.page_bbox = None
        self.logger = logger.getChild('imagehandler')
        self.pdf = pdf

    def _get_image(self, xref: str) -> LImage:
        image = self.pdf.extract_image(xref)
        self.logger.debug(f"Loading image {xref}")
        if image:
            self.logger.debug(f"Image {xref}: found")
            pix = fitz.Pixmap(image['image'])

            #Convert CMYK to RGB
            invert = False
            if 'colorspace' in image and image['cs-name'] != 'DeviceRGB':
                self.logger.debug(f"Image {xref}: in colorspace {image['cs-name']}")
                pix = fitz.Pixmap(fitz.csRGB, pix)
                if image['cs-name'] == 'DeviceCMYK':
                    invert = True
            mode = 'RGB'

            #Load SMASK as alpha channel
            if 'smask' in image and image['smask'] > 0:
                self.logger.debug(f"Image {xref}: found smask with xref {image['smask']}")
                mask = fitz.Pixmap(self.pdf.extract_image(image['smask'])['image'])
                try:
                    pix = fitz.Pixmap(pix, mask)
                    mode = 'RGBA'
                except:
                    self.logger.warning(f"Failed to create mask for image xref {xref}")
            else:
                mode = 'RGB'

            pil_image = PILImage.open(io.BytesIO(pix.tobytes()))

            #Handle CMYK inverting
            if invert:
                self.logger.debug(f"Image {xref}: inverting")
                channels = [c for c in pil_image.split()]
                for i in range(0, 3):
                    channels[i] = PIL.ImageOps.invert(channels[i])
                    pil_image = PILImage.merge(mode, channels)

            return pil_image
        return None

    def _classify_image(self, imageData: LImage) -> LImage.ImageType:
    
        #Calculate visible area of image intersected with visible area of page
        x_coverage = round(imageData.bbox.x_overlap(self.page_bbox, 'second'), 3)
        y_coverage = round(imageData.bbox.y_overlap(self.page_bbox, 'second'), 3)
        page_coverage =  x_coverage * y_coverage

        image = np.asarray(imageData.image)[:,:,:3]
        x_variance = round(np.median(image.var(axis=0), axis=0).mean(), 2)
        y_variance = round(np.median(image.var(axis=1), axis=0).mean(), 2)

        extrema = imageData.image.getextrema()
        if len(extrema) == 2:
            extrema = [extrema]
        maxExtrema = max([b-a for a,b in extrema])
        
        imageData.properties['variance'] = {'x':x_variance, 'y':y_variance}
        imageData.properties['coverage'] = {'x':x_coverage, 'y':y_coverage, 'page':page_coverage}
        imageData.properties['extrema'] = maxExtrema


        self.logger.debug(f"Image properties :{imageData.properties}")

        #If cover is too small, we can't see it
        if page_coverage <= 0.001:
            return LImage.ImageType.Invisible

        #If thin in one dimension, treat as line rather than image
        if (x_coverage < 0.05 and y_coverage > 0.1) or (x_coverage > 0.1 and y_coverage < 0.05):
            return LImage.ImageType.Line

        #If it's too small in any particular dimension it can't be a meaningful image
        if x_coverage < 0.05 or y_coverage < 0.05 or page_coverage < 0.05:
            return LImage.ImageType.Decorative

        #If complexity is low it could be either a full page background or a section
        if x_variance < 50 and y_variance < 50 and maxExtrema < 100:
            if page_coverage > 0.9:
                return LImage.ImageType.Background
            elif page_coverage > 0.1:
                return LImage.ImageType.Section
            else:
                return LImage.ImageType.Decorative

        if (x_variance < 50 and y_variance > 1000) or (x_variance > 1000 and y_variance < 50):
            return LImage.ImageType.Gradient

        if page_coverage < 0.05 or x_coverage < 0.15 or y_coverage < 0.15:
            return LImage.ImageType.Decorative

        return LImage.ImageType.Primary

    def _crop_to_visible(self, orig_bbox: Bbox, image: PILImage.Image) -> Tuple[PILImage.Image, Bbox]:
        '''Crop an image to only the visible pixels while preserving scaling transformations from the original PDF'''
        new_bbox = image.getbbox()

        scale_factor_x = (orig_bbox.x1 - orig_bbox.x0) / image.size[0]
        scale_factor_y = (orig_bbox.y1 - orig_bbox.y0) / image.size[1]

        new_x0 = orig_bbox.x0 + new_bbox[0]*scale_factor_x
        new_y0 = orig_bbox.y0 + new_bbox[1]*scale_factor_y

        new_width = (new_bbox[2] - new_bbox[0]) * scale_factor_x
        new_height = (new_bbox[3] - new_bbox[1]) * scale_factor_y

        crop_bbox = image.getbbox()
        image = image.crop(crop_bbox)
        new_bbox = Bbox(
            new_x0, 
            new_y0, 
            new_x0 + new_width, 
            new_y0 + new_height,
            self.page_bbox.page_width,
            self.page_bbox.page_height
        )
        self.logger.debug(f"Scaled image with factors ({scale_factor_x},{scale_factor_y})")
        self.logger.debug(f"Original Bbox: {orig_bbox}")
        self.logger.debug(f"New Bbox: {new_bbox}")
        return (image, new_bbox)
                    
    def get_page_images(self, page: fitz.Page) -> List[LImage]:
        self.logger.debug("Starting image extraction")
        
        bound = page.bound()
        self.page_bbox = Bbox(*bound, bound[2], bound[3])
        images = page.get_image_info(hashes=False, xrefs=True)
        processed_images = {t.name:[] for t in LImage.ImageType}

        for i in images:
            image = self._get_image(i['xref'])

            if image:
                orig_bbox = Bbox(*i['bbox'], bound[2], bound[3])
                image, crop_bbox = self._crop_to_visible(orig_bbox, image)
                im = LImage(None, crop_bbox, orig_bbox,
                    image, {})
                im.type = self._classify_image(im)
                processed_images[im.type.name].append(im)

        for t in processed_images:
            self.logger.debug(f"Found {len(processed_images[t])} {t} images")
        return processed_images