import logging
import multiprocessing as mp
import os
from typing import Any, Dict, List, Optional, Tuple, Type

import fitz

from .processors.aggregator_processor import AggregatorProcessor
from .processors.content_processor import ContentProcessor
from .processors.json_out_processor import JSONOutProcessor
from .processors.layout_processor import LayoutProcessor
from .processors.margin_processor import MarginProcessor
from .processors.pdf_load_processor import PDFLoadProcessor
from .processors.processor import Processor
from .processors.reading_order_processor import ReadingOrderProcessor
from .processors.rules_table_processor import RulesTableProcessor

try:
    from .processors.ml_table_processor import MLTableProcessor
    _HAS_TRANSFORMERS = True
except ImportError:
    _HAS_TRANSFORMERS = False

from .utils.logging import get_logger
from .utils.render_pages import render_pages


class BurdocParser(object):

 
    def __init__(self,
                 use_ml_table_finding: bool=True,
                 extract_images: bool=False,
                 generate_page_images: bool=False,
                 max_threads: Optional[int]=None,
                 log_level: int=logging.INFO,
                 do_render_pages: bool=False,
        ):
        
        self.log_level = log_level
        self.logger = get_logger("burdoc_parser", log_level=log_level)
        self.min_slice_size = 100
        self.max_slices = 12
        self.max_threads = max_threads
        self.render = do_render_pages

        self.processors: List[Tuple[Type[Processor], Dict, bool]] = [
           (PDFLoadProcessor, {}, True),
        ]
        if _HAS_TRANSFORMERS and use_ml_table_finding:
            self.processors.append(
                (MLTableProcessor, {}, False)
            )

        self.processors.append(
           (AggregatorProcessor, {
            'processors': [
                MarginProcessor,
                LayoutProcessor,
                RulesTableProcessor,
                ReadingOrderProcessor,
                ContentProcessor,
                JSONOutProcessor
            ],
            'render_processors': [
                True, True, True, True, True, False
            ],
            'processor_args': [{}, {}, {}, {}, {}, {'extract_images':extract_images}],
            'additional_reqs': ['tables'] if use_ml_table_finding else []
           }, True, )
        )

        self.return_fields = ['metadata', 'content', 'page_hierarchy']
        
        if extract_images:
            self.return_fields.append("images")
        
        if generate_page_images:
            self.return_fields.append("page_images")

    @staticmethod
    def _process_slice(arg_dict: Any) -> Dict[str, Any]:
        pa = arg_dict['processor_args']
        processor = arg_dict['processor'](**pa)
        processor.initialise()
        processor.process(arg_dict['data'])
        return {k:arg_dict['data'][k] for k in ['metadata'] + processor.generates()}

    def slice_data(self, data: Dict[str, Any], page_slices: List[List[int]], requirements: Tuple[List[str], List[str]]):
        keys = requirements[0] + [k for k in requirements[1] if k in data]
        sliced_data = [
            {'metadata':data['metadata'], 'slice': ps} | \
            {k:{p:data[k][p] for p in ps} for k in keys}
        for ps in page_slices]
        return sliced_data

    def merge_data(self, original_data: Dict[str, Any], sliced_data: List[Dict[str, Any]], new_fields: List[str]):

        for f in new_fields:
            if f not in original_data:
                original_data[f] = {}

        for sd in sliced_data:
            for k in new_fields:
                    original_data[k] |= sd[k]
        original_data['metadata'] |= sliced_data[0]['metadata']
        return original_data 
        

    def run_processor(self, processor: Type[Processor], processor_args: Dict[str, Any], 
                      pages: List[int], data: Dict[str, Any]):
        
        self.logger.debug(f"========================= Running {type(processor).__name__} ===========================")

        if len(pages) > 1 and (not self.max_threads or self.max_threads > 1) and processor.threadable:
            slice_size = max(self.min_slice_size, int(len(pages) / self.max_slices))
            page_slices = [pages[i*slice_size:(i*slice_size)+slice_size] for i in range(int(len(pages)/slice_size))]
            if len(pages) % slice_size != 0:
                page_slices.append(pages[len(page_slices)*slice_size:])
        else:
            page_slices = [pages]

        self.logger.debug(f"Page slices={page_slices}")

        proc = processor(**processor_args, log_level=self.log_level)
        data_slices = self.slice_data(data, page_slices, proc.requirements())
        thread_args = [{
            'processor':processor, 
            'processor_args': {
                **processor_args, 'log_level': self.log_level
            } ,
            'data': ds
        } for ds in data_slices]

        if len(page_slices) > 1:
            with mp.Pool(self.max_threads if (self.max_threads and self.max_threads > 1) else None) as p:
                sliced_results = p.map(BurdocParser._process_slice, thread_args, chunksize=1)
        else:
            sliced_results = [BurdocParser._process_slice(thread_args[0])]

        self.merge_data(data, sliced_results, proc.generates())

    def read(self, path: os.PathLike, pages: Optional[List[int]]=None) -> Any:
        
        pdf = fitz.open(path)
        if not pages:
            pages = [i for i in range(pdf.page_count)]
        else:
            pages = [int(p) for p in pages if p < pdf.page_count]
        pdf.close()

        data = {'metadata':{'path':path}}
        renderers = []

        for p,args,render_p in self.processors:
            self.run_processor(p, args, pages, data)
            if render_p:
                renderers.append(p(**args, log_level=self.log_level))

        if self.render:
            render_pages(data, renderers)

        return {k:data[k] for k in self.return_fields}






