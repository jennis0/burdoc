import base64
import hashlib
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

import fitz
import numpy as np
from PIL import Image
from PIL.ImageFilter import GaussianBlur

from ...elements import Bbox, ImageElement, ImageType
from ...utils.image_manip import get_image_palette
from ...utils.logging import get_logger


class ImageHandler():
    """Extracts Images from a PDF, applies common preprocessing such as merging smasks and correcting inverted storage
    formats then classifies them according to their purpose within the document.
    """

    def __init__(self, pdf: fitz.Document, log_level: int = logging.INFO):
        self.cache: Dict[str, Any] = {}
        self.logger = get_logger('image-handler', log_level=log_level)
        self.pdf = pdf

    def _get_image(self, xref: str) -> Optional[Image.Image]:
        
        if xref == 0:
            return None
        
        image = self.pdf.extract_image(xref)
        
        self.logger.debug("Loading image %d", xref)
        if image:
            self.logger.debug("Image %d: found", xref)
            # pix = fitz.Pixmap(image['image'])
            pil_image = Image.open(io.BytesIO(image['image']))

            # CMYK is generally inverted when stored in JPEGs. 
            # PIL doesn't natively support CMYK inversion so do it ourselves.
            if 'colorspace' in image and image['cs-name'] == 'DeviceCMYK':
                image_filter = self.pdf.xref_get_key(xref, 'Filter')
                if image_filter[1] == '/DCTDecode':
                    image_data = np.frombuffer(pil_image.tobytes(), dtype='B')
                    inverse_data = np.full(image_data.shape, 255, dtype='B')
                    inverse_data -= image_data
                    pil_image = Image.frombytes(
                        pil_image.mode, pil_image.size, inverse_data.tobytes())

            # #Load SMASK as alpha channel
            if 'smask' in image and image['smask'] > 0:
                self.logger.debug(
                    "Image %d: found softmask with xref %d", xref, image['smask'])
                mask = self.pdf.extract_image(image['smask'])
                mask_image = Image.open(io.BytesIO(mask['image']))
                
                if pil_image.size != mask_image.size:
                    mask_image = mask_image.resize(pil_image.size)
                pil_image.putalpha(mask_image)

            return pil_image
        return None

    def _classify_image(self, image_element: ImageElement, image: Image.Image, page_colour: np.ndarray, page_bbox: Bbox) -> ImageType:
        """Apply basic classification to the image to try and determine it's role.

        Args:
            image_element (ImageElement): The LayoutElement of the image
            image (Image.Image): The image itself
            page_colour (np.ndarray): Background colour of the page
            page_bbox (Bbox): Bounding box of the page

        Returns:
            ImageType: The estimated image type
        """

        # If cover is too small, we can't see it
        x_coverage = round(
            image_element.bbox.x_overlap(page_bbox, 'second'), 3)
        y_coverage = round(
            image_element.bbox.y_overlap(page_bbox, 'second'), 3)
        page_coverage = x_coverage * y_coverage
                
        if page_coverage <= 0.0001:
            return ImageType.INVISIBLE

        # If thin in one dimension, treat as line rather than image
        if ((x_coverage < 0.05 and y_coverage > 0.1) or (x_coverage > 0.1 and y_coverage < 0.05)):
            if image_element.bbox.y1_norm() > 0.1 and image_element.bbox.y0_norm() < 0.9:
                return ImageType.LINE
            else:
                return ImageType.DECORATIVE
            
        # Now we've covered basic size-based cases, handle more complex image processing
        reduced_image = image.crop([image.size[0]*0.33, image.size[1]*0.33,
                                    image.size[0]*0.66, image.size[1]*0.66])

        gaussian_filter = GaussianBlur(radius=10)
        blurred_image = reduced_image.filter(gaussian_filter)
        reduced_image = np.asarray(blurred_image)

        x_variance = round(
            np.median(reduced_image.var(axis=0), axis=0).mean(), 2)
        y_variance = round(
            np.median(reduced_image.var(axis=1), axis=0).mean(), 2)

        extrema = blurred_image.getextrema()
        if len(extrema) == 2:
            extrema = [extrema]
        max_extrema = max(b-a for a, b in extrema[:3])

        image_element.properties['variance'] = {
            'x': x_variance, 'y': y_variance}
        image_element.properties['coverage'] = {
            'x': x_coverage, 'y': y_coverage, 'page': page_coverage}
        image_element.properties['extrema'] = max_extrema

        palette = get_image_palette(image, 5, n_means=5)

        image_element.properties['palette'] = palette

        image_element.properties['primary_colour'] = np.array(
            palette[0][0])
        
        #Calculate distance between primary and other colours. Useful indicator of a monochrome image that
        #can't be used for section backing
        dist = 0
        for i in range(1, len(palette)):
            
            #Ignore anything that doesn't make up enough of the image
            if palette[i][1] < 0.16:
                break
            arr = np.array(palette[i][0])
            
            #Ignore anything too close to black - can be lines/shadow
            if arr.mean() < 10:
                continue
            
            dist = max(dist, np.linalg.norm(np.array(palette[0][0]) - np.array(arr)).sum())
        image_element.properties['colour_distance'] = dist
        
        if 'A'  in image.getbands():
            image_element.properties['alpha'] = np.mean(image.getchannel('A'))
        else:
            image_element.properties['alpha'] = 255.

        colour_offset = image_element.properties['primary_colour'] - page_colour
        image_element.properties['colour_offset'] = np.linalg.norm(colour_offset).sum()

        self.logger.debug("Image properties : %s",
                          str(image_element.properties))
        
        # If complexity is low it could be either a full page background or a section
        if x_variance + y_variance < 200 and image_element.properties['alpha'] > 100 and \
            not (image_element.properties['colour_distance'] > 50 and palette[1][1] > 0.2):
            if page_coverage > 0.9:
                return ImageType.BACKGROUND

            if page_coverage > 0.1 and image_element.properties['colour_offset'] > 15:
                return ImageType.SECTION

        if ((x_variance < 50 and y_variance > 1000) or (x_variance > 1000 and y_variance < 50)) and image_element.properties['colour_distance'] > 50.:
            return ImageType.GRADIENT

        is_on_page_edge = image_element.bbox.x1_norm() < 0.08 or image_element.bbox.x0_norm() > 0.92 or \
            image_element.bbox.y1_norm() < 0.08 or image_element.bbox.y0_norm() > 0.92
                        
        if (page_coverage < 0.05 or x_coverage < 0.15 or y_coverage < 0.15) and is_on_page_edge:
            return ImageType.DECORATIVE

        return ImageType.PRIMARY

    def _crop_to_visible(self, orig_bbox: Bbox, image: Image.Image, page_bound: Bbox) -> Tuple[Image.Image, Bbox]:
        """Crops an image to only the pixels that are visible on the page, while preserving scaling transformations
        from the original PDF

        Args:
            orig_bbox (Bbox): Full Bounding box of the image
            image (Image.Image): The Image itself
            page_bound (Bbox): Bounding box of the page

        Returns:
            Tuple[Image.Image, Bbox]: Cropped image and it's new Bbox
        """
        new_bbox = image.getbbox()

        if not new_bbox:
            return (image, orig_bbox)
        
        scale_factor_x = orig_bbox.width() / image.size[0]
        scale_factor_y = orig_bbox.height() / image.size[1]

        new_x0 = max(orig_bbox.x0 + new_bbox[0]*scale_factor_x, 0)
        new_y0 = max(orig_bbox.y0 + new_bbox[1]*scale_factor_y, 0)

        new_width = min((new_bbox[2] - new_bbox[0])
                        * scale_factor_x, page_bound.x1 - new_x0)
        new_height = min((new_bbox[3] - new_bbox[1])
                         * scale_factor_y, page_bound.y1 - new_y0)

        crop_bbox = image.getbbox()
        image = image.crop(crop_bbox)
        new_bbox = Bbox(
            new_x0,
            new_y0,
            new_x0 + new_width,
            new_y0 + new_height,
            page_bound.page_width,
            page_bound.page_height
        )
        self.logger.debug("Scaled image with factors (%f,%f)",
                          scale_factor_x, scale_factor_y)
        self.logger.debug("Original Bbox: %s", str(orig_bbox))
        self.logger.debug("New Bbox: %s", str(new_bbox))
        return (image, new_bbox)

    def merge_images(self, images: List[ImageElement], image_store: List[Image.Image]):
        used_images = [False for i in images]

        for i, im1 in enumerate(images):
            im1_pil = image_store[im1.image]

            if im1.bbox.width(norm=True) > 0.95 and im1.bbox.height(norm=True) > 0.95:
                continue

            if used_images[i]:
                continue
            for j, im2 in enumerate(images[i+1:]):
                if used_images[j+i+1]:
                    continue

                if im2.bbox.width(norm=True) > 0.95 and im2.bbox.height(norm=True) > 0.95:
                    continue

                im2_pil = image_store[im2.image]

                if im2.bbox.overlap(im1.bbox, "first") > 0.7:
                    im1_pil.paste(
                        im2_pil, (int(im2.bbox.x0-im1.bbox.x0),
                                  int(im2.bbox.y0-im1.bbox.y0))
                    )
                    im1.bbox = Bbox.merge([im1.bbox, im2.bbox])
                    im1.original_bbox = Bbox.merge(
                        [im1.original_bbox, im2.original_bbox])
                    used_images[j+i+1] = True
                    images[i] = im1
                elif im2.bbox.overlap(im1.bbox, "second") > 0.7:
                    im2_pil.paste(
                        im1_pil, (int(im1.bbox.x0-im2.bbox.x0),
                                  int(im1.bbox.y0-im2.bbox.y0))
                    )
                    im1_pil = im2_pil
                    im1.bbox = Bbox.merge([im1.bbox, im2.bbox])
                    im1.original_bbox = Bbox.merge(
                        [im1.original_bbox, im2.original_bbox])
                    used_images[j+i] = True
                    images[i] = im1

        return [i for i, u in zip(images, used_images) if not u]

    def get_image_elements(self, page: fitz.Page, page_image: Image.Image, page_colour: np.ndarray) -> Tuple[Dict[ImageType, List[ImageElement]], List[Image.Image]]:
        """Extracts images from a PDF page.

        Args:
            page (fitz.Page): PDF Page to extract from 
            page_image (Image.Image): An image of the page, used to identify the role of each image
            page_colour (np.ndarray): The primary background colour of the page

        Returns:
            Tuple[Dict[ImageType, List[ImageElement]], List[Image.Image]]: A list of each possible image type
        """
        self.logger.debug("Starting image extraction")

        bound = page.bound()
        page_bbox = Bbox(*bound, bound[2], bound[3])  # type:ignore
        page_images = page.get_image_info(hashes=False, xrefs=True)

        image_elements: Dict[ImageType, List[ImageElement]] = {
            image_type: [] for image_type in ImageType
        }
        images: List[str] = []

        for page_image in page_images:
            image = self._get_image(page_image['xref'])

            if image:
                
                orig_bbox = Bbox(
                    *page_image['bbox'], bound[2], bound[3])  # type:ignore

                image, crop_bbox = self._crop_to_visible(
                    orig_bbox, image, page_bbox)
                if not image:
                    continue

                image_element = ImageElement(bbox=crop_bbox, original_bbox=orig_bbox,
                                             image_type=ImageType.PRIMARY,
                                             image=-1, properties={})

                image_element.type = self._classify_image(
                    image_element, image, page_colour, page_bbox)
                
                image_elements[image_element.type].append(image_element)

                image_as_bytes = io.BytesIO()
                image.save(image_as_bytes, 'webp')
                image_as_str = base64.b64encode(image_as_bytes.getbuffer())

                im_hash = hashlib.md5(
                    image_as_str, usedforsecurity=False).hexdigest()
                if im_hash not in self.cache:
                    images.append(image_as_str.decode('utf-8'))
                    self.cache[im_hash] = len(images) - 1

                image_element.image = self.cache[im_hash]

        # if ImageType.PRIMARY in image_elements:
        #     image_elements[ImageType.PRIMARY] = self.merge_images(image_elements[ImageType.PRIMARY], images)

        for image_type in image_elements:
            self.logger.debug("Found %d %s images", len(
                image_elements), image_type.name)

        return image_elements, images
