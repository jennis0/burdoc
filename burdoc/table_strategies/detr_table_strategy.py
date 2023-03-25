
from transformers import DetrImageProcessor, TableTransformerForObjectDetection
from PIL import Image
import logging
import torch
from typing import Any, List, Dict, Optional

import time

from .table_extractor_strategy import TableExtractorStrategy
from ..elements.bbox import Bbox

class DetrTableStrategy(TableExtractorStrategy):


    def __init__(self, log_level: Optional[int]=logging.INFO):
        super().__init__('detr', log_level=log_level)

        self.margin = 25
        self.threshold = 0.9
        self.extractor = DetrImageProcessor()
        self.detector_model = TableTransformerForObjectDetection.from_pretrained('microsoft/table-transformer-detection')
        self.structure_model = TableTransformerForObjectDetection.from_pretrained('microsoft/table-transformer-structure-recognition')

        if torch.cuda.is_available():
            self.logger.debug("Found CUDA")
            self.cuda = True
            self.device = torch.cuda.current_device()
            self.detector_model.to(self.device)
            self.structure_model.to(self.device)
            self.batch_size = 10
        else:
            self.cuda = False
            self.batch_size = -1


    @staticmethod
    def requirements() -> List[str]:
        return ['page_images']

    def extract_tables(self, page_numbers: List[int], page_images: Dict[int, Image.Image]) -> Dict[int, Any]:

        i = 0
        results = {}
        while i < len(page_images):
            batch_images = list(page_images.values())[i:i+self.batch_size]
            batch_page_numbers = page_numbers[i:i+self.batch_size]

            res = self._extract_tables_batch(batch_images)
            for bpn,r in zip(batch_page_numbers, res):
                results[bpn] = r
            i += self.batch_size

        return results
    

    def _preprocess_image(self, page_images: List[Image.Image], remove_background: bool):
        page_images = [i.convert("RGB") for i in page_images]
        s = time.time()
        encoding = self.extractor.preprocess(page_images, return_tensors='pt', 
                                             do_resize=True, do_rescale=True, do_normalize=True)
        self.logger.debug(f"Encoding {round(time.time() - s, 2)}")
        return encoding

    def _do_extraction(self, model, images: List[Image.Image], remove_background: bool):
        features = self._preprocess_image(images, remove_background)
        sizes = torch.tensor([[i.size[1], i.size[0]] for i in images])
        if self.cuda:
            features.to(self.device)
            sizes = sizes.to(self.device)
        with torch.no_grad():
            s = time.time()
            outputs = model(**features)
            self.logger.debug(f"Model {round(time.time() - s, 2)}")
        
        s = time.time()
        results = self.extractor.post_process_object_detection(outputs, threshold=0.7, target_sizes=sizes)
        self.logger.debug(f"Postprocess {round(time.time() - s, 2)}")
        return results

    def _extract_tables_batch(self, page_images: List[Image.Image]) -> List[Any]:
        results = self._do_extraction(self.detector_model, page_images, True)

        table_images = []
        table_pages = []
        bbox_corrections = []
        for i,r in enumerate(results):
            if len(r['boxes']) > 0:
                for s,b in zip(r['scores'], r['boxes']):
                    if s < self.threshold:
                        continue
                    crop_box = [
                        max(0, int(b[0].item()-self.margin)),
                        max(0, int(b[1].item()-self.margin)),
                        min(page_images[i].size[0], int(b[2].item()+self.margin)),
                        min(page_images[i].size[1], int(b[3].item()+self.margin)),

                    ]
                    bbox_corrections.append([crop_box[0], crop_box[1]])
                    table_images.append(page_images[i].crop(crop_box))
                    table_pages.append(i)
        
        if len(table_images) == 0:
            return []

        results = self._do_extraction(self.structure_model, table_images, False)

        tables = [[] for _ in range(len(page_images))]
        for p,c,t in zip(table_pages, bbox_corrections, results):
            tables[p].append(self._prepare_table(t,  c, *page_images[p].size)) 
        
        return tables

    def _prepare_table(self, results, corrections, page_width, page_height) -> Any:
        parts = []
        table = None
        bbox_offset_x = 3
        bbox_offset_y = 3
        for label,score,bbox in zip(results['labels'].tolist(), results['scores'].tolist(), results['boxes'].tolist()):
            corrected_bb = [bbox[0]+corrections[0]-bbox_offset_x, bbox[1]+corrections[1]-bbox_offset_y, 
                            bbox[2]+corrections[0]+bbox_offset_x, bbox[3]+corrections[1]+bbox_offset_y]
            part_type = TableExtractorStrategy.TableParts._value2member_map_[label]
            if part_type == TableExtractorStrategy.TableParts.Table:
                table = (TableExtractorStrategy.TableParts._value2member_map_[label], Bbox(*corrected_bb, page_width, page_height), score)
            else:
                parts.append((TableExtractorStrategy.TableParts._value2member_map_[label], Bbox(*corrected_bb, page_width, page_height), score))
        return (table, parts)
