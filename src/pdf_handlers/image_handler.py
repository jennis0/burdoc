from PIL import Image as PILImage
from PIL.ImageFilter import GaussianBlur

import fitz
import hashlib
import numpy as np
import logging
import io
from typing import List, Tuple
from ..elements.bbox import Bbox
from ..elements.layout_objects import ImageElement

from ..utils.image_manip import get_image_palette

import plotly.express as plt


class ImageHandler(object):

    def __init__(self, logger: logging.Logger, pdf: fitz.Document):
        self.cache = {}
        self.page_bbox = None
        self.logger = logger.getChild('imagehandler')
        self.pdf = pdf

    def _get_image(self, xref: str) -> ImageElement:
        image = self.pdf.extract_image(xref)
        self.logger.debug(f"Loading image {xref}")
        if image:
            self.logger.debug(f"Image {xref}: found")
            pix = fitz.Pixmap(image['image'])

            #Convert CMYK to RGB
            if 'colorspace' in image and image['cs-name'] != 'DeviceRGB':
                self.logger.debug(f"Image {xref}: in colorspace {image['cs-name']}")
                pix = fitz.Pixmap(fitz.csRGB, pix)
                if image['cs-name'] == 'DeviceCMYK':
                    self.logger.debug("Inverting CMYK image")
                    pix.invert_irect()

            #Load SMASK as alpha channel
            if 'smask' in image and image['smask'] > 0:
                self.logger.debug(f"Image {xref}: found softmask with xref {image['smask']}")
                mask = self.pdf.extract_image(image['smask'])
                mask_image = fitz.Pixmap(mask['image'])
                try:
                    if mask_image.height != pix.height or mask_image.width != pix.width:
                        self.logger.debug("Rescaling image softmask")
                        mask_image = fitz.Pixmap(mask_image, pix.width, pix.height, None)
                    pix = fitz.Pixmap(pix, mask_image)
                except Exception as e:
                    self.logger.warning(f"Failed to create mask for image xref {xref}")
                    self.logger.error(e)

            return PILImage.open(io.BytesIO(pix.tobytes()))
        return None

    def _classify_image(self, imageData: ImageElement, page_colour: np.array) -> ImageElement.ImageType:
    
        #Calculate visible area of image intersected with visible area of page
        x_coverage = round(imageData.bbox.x_overlap(self.page_bbox, 'second'), 3)
        y_coverage = round(imageData.bbox.y_overlap(self.page_bbox, 'second'), 3)
        page_coverage =  x_coverage * y_coverage

        image = np.asarray(imageData.image)[:,:,:3]

        x_dims = int(0.25*image.shape[0]), int(0.75*image.shape[0])
        y_dims = int(0.25*image.shape[1]), int(0.75*image.shape[1])

        
        filter = GaussianBlur(radius=10)
        blurred_image = imageData.image.filter(filter)
        reduced_image = np.asarray(blurred_image)[x_dims[0]:x_dims[1],y_dims[0]:y_dims[1]]

        x_variance = round(np.median(reduced_image.var(axis=0), axis=0).mean(), 2)
        y_variance = round(np.median(reduced_image.var(axis=1), axis=0).mean(), 2)

        extrema = blurred_image.getextrema()
        if len(extrema) == 2:
            extrema = [extrema]
        maxExtrema = max([b-a for a,b in extrema[:3]])
        
        imageData.properties['variance'] = {'x':x_variance, 'y':y_variance}
        imageData.properties['coverage'] = {'x':x_coverage, 'y':y_coverage, 'page':page_coverage}
        imageData.properties['extrema'] = maxExtrema

        imageData.properties['primary_colour'] = np.array(get_image_palette(imageData.image, 1)[0][0])
        
        colour_offset = imageData.properties['primary_colour'] - page_colour
        imageData.properties['colour_offset'] = np.sqrt(np.sum(colour_offset*colour_offset))

        self.logger.debug(f"Image properties :{imageData.properties}")

        #If cover is too small, we can't see it
        if page_coverage <= 0.001:
            return ImageElement.ImageType.Invisible

        #If thin in one dimension, treat as line rather than image
        if ((x_coverage < 0.05 and y_coverage > 0.1) or (x_coverage > 0.1 and y_coverage < 0.05)):
            if (imageData.bbox.y1 / self.page_bbox.y1) > 0.1 and (imageData.bbox.y0 / self.page_bbox.y1) < 0.9:
                return ImageElement.ImageType.Line
            else:
                return ImageElement.ImageType.Decorative

        #If it's too small in any particular dimension it can't be a meaningful image
        if x_coverage < 0.05 or y_coverage < 0.05 or page_coverage < 0.05:
            return ImageElement.ImageType.Decorative

        #If complexity is low it could be either a full page background or a section
        if x_variance + y_variance < 200:
            if page_coverage > 0.9:
                return ImageElement.ImageType.Background
            elif page_coverage > 0.1 and imageData.properties['colour_offset'] > 15:
                return ImageElement.ImageType.Section
            else:
                return ImageElement.ImageType.Decorative

        if (x_variance < 50 and y_variance > 1000) or (x_variance > 1000 and y_variance < 50):
            return ImageElement.ImageType.Gradient

        if page_coverage < 0.05 or x_coverage < 0.15 or y_coverage < 0.15:
            return ImageElement.ImageType.Decorative

        return ImageElement.ImageType.Primary

    def _crop_to_visible(self, orig_bbox: Bbox, image: PILImage.Image, page_bound: Bbox) -> Tuple[PILImage.Image, Bbox]:
        '''Crop an image to only the visible pixels while preserving scaling transformations from the original PDF'''
        new_bbox = image.getbbox()

        if not new_bbox:
            return (None, None)

        scale_factor_x = (orig_bbox.x1 - orig_bbox.x0) / image.size[0]
        scale_factor_y = (orig_bbox.y1 - orig_bbox.y0) / image.size[1]

        new_x0 = max(orig_bbox.x0 + new_bbox[0]*scale_factor_x, 0)
        new_y0 = max(orig_bbox.y0 + new_bbox[1]*scale_factor_y, 0)

        new_width = min((new_bbox[2] - new_bbox[0]) * scale_factor_x, page_bound.x1 - new_x0)
        new_height = min((new_bbox[3] - new_bbox[1]) * scale_factor_y, page_bound.y1 - new_y0)

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
    
    def merge_images(self, images: List[ImageElement], image_store: List[PILImage.Image]):
        used_images = [False for i in images]

        for i in range(len(images)):
            im1 = images[i]
            im1_pil = image_store[im1.image]

            if im1.bbox.width(norm=True) > 0.95 and im1.bbox.height(norm=True) > 0.95:
                continue

            if used_images[i]:
                continue
            for j,im2 in enumerate(images[i+1:]):
                if used_images[j+i+1]:
                    continue

                if im2.bbox.width(norm=True) > 0.95 and im2.bbox.height(norm=True) > 0.95:
                    continue

                im2_pil = image_store[im2.image]

                if im2.bbox.overlap(im1.bbox, "first") > 0.7:
                    im1_pil.paste(
                        im2_pil, (int(im2.bbox.x0-im1.bbox.x0), int(im2.bbox.y0-im1.bbox.y0))
                    )
                    im1.bbox = Bbox.merge([im1.bbox, im2.bbox])
                    im1.original_bbox = Bbox.merge([im1.original_bbox, im2.original_bbox])
                    used_images[j+i+1] = True
                    images[i] = im1
                elif im2.bbox.overlap(im1.bbox, "second") > 0.7:
                    im2_pil.paste(
                        im1_pil, (int(im1.bbox.x0-im2.bbox.x0), int(im1.bbox.y0-im2.bbox.y0))
                    )
                    im1_pil = im2_pil
                    im1.bbox = Bbox.merge([im1.bbox, im2.bbox])
                    im1.original_bbox = Bbox.merge([im1.original_bbox, im2.original_bbox])
                    used_images[j+i] = True
                    images[i] = im1

        return [i for i,u in zip(images, used_images) if not u]

                    
    def get_page_images(self, page: fitz.Page, page_image: PILImage) -> List[ImageElement]:
        self.logger.debug("Starting image extraction")

        page_colour = np.array(get_image_palette(page_image, 1)[0][0])
        
        bound = page.bound()
        self.page_bbox = Bbox(*bound, bound[2], bound[3])
        images = page.get_image_info(hashes=False, xrefs=True)
        processed_images = {t:[] for t in ImageElement.ImageType}

        image_store = []

        for i in images:
            image = self._get_image(i['xref'])

            if image:
                orig_bbox = Bbox(*i['bbox'], bound[2], bound[3])
                image, crop_bbox = self._crop_to_visible(orig_bbox, image, self.page_bbox)
                if not image:
                    continue
                im = ImageElement(bbox=crop_bbox, original_bbox=orig_bbox, type=None,
                    image=image, properties={})
                im.type = self._classify_image(im, page_colour)
                processed_images[im.type].append(im)

                hash = hashlib.md5(im.image.tobytes()).hexdigest()
                if hash not in self.cache:
                    image_store.append(im.image)
                    self.cache[hash] = len(image_store) - 1

                im.image = self.cache[hash]

        if ImageElement.ImageType.Primary in processed_images:
            processed_images[ImageElement.ImageType.Primary] = self.merge_images(processed_images[ImageElement.ImageType.Primary], image_store)

        for t in processed_images:
            self.logger.debug(f"Found {len(processed_images[t])} {t} images")

        return processed_images, image_store