import logging
import os
import multiprocessing as mp
import logger_tt
import fitz
import numpy as np

from typing import Any, Dict, List, Optional


from .processors.processor import Processor
from .processors.pdf_load_processor import PDFLoadProcessor
from .processors.ml_table_processor import MLTableProcessor
from .processors.layout_processor import LayoutProcessor
from .processors.reading_order_processor import ReadingOrderProcessor
from .processors.margin_processor import MarginProcessor
from .processors.content_processor import ContentProcessor
from .processors.json_out_processor import JSONOutProcessor
from .processors.aggregator_processor import AggregatorProcessor
from .processors.processor import Processor
from .processors.rules_table_processor import RulesTableProcessor

from .utils.render_pages import render_pages

class Burdoc(object):

    def __init__(self, 
                 log_level: int=logging.INFO, 
                 render_pages: bool=False,
                 ):
        self.log_level = log_level

        logger_tt.setup_logging(
            log_path="burdoc.log", suppress_level_below=log_level,
            full_context=2,
            use_multiprocessing=True, suppress=['logger_tt', 'pytorch', 'timm', 'PIL']
        )
        self.logger = logger_tt.getLogger('burdoc')
        self.min_slice_size = 100
        self.max_slices = 12
        self.max_threads = None
        self.render = render_pages

        self.processors = [
           (PDFLoadProcessor, {}, True),
           (MLTableProcessor, {}, False),
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
            'processor_args': [{}, {}, {}, {}, {}, {}],
            'additional_reqs': ['tables']
           }, True, )
        ]

        self.return_fields = ['metadata', 'json', 'page_hierarchy']

    @staticmethod
    def _process_slice(arg_dict: Any) -> Dict[str, Any]:
        pa = arg_dict['processor_args']
        processor = arg_dict['processor'](**pa)
        processor.initialise()
        processor.process(arg_dict['data'])
        return {k:arg_dict['data'][k] for k in ['metadata'] + processor.generates()}

    def slice_data(self, data: Dict[str, Any], page_slices: List[List[int]], requirements: List[str]):
        sliced_data = [
            {'metadata':data['metadata'], 'slice': ps} | \
            {k:{p:data[k][p] for p in ps} for k in requirements}
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
        

    def run_processor(self, processor: Processor, processor_args: Dict[str, Any], 
                      pages: List[int], data: Dict[str, Any]) -> Dict[str, Any]:
        
        self.logger.debug(f"========================= Running {type(processor).__name__} ===========================")

        if len(pages) > 1 and (not self.max_threads or self.max_threads > 1) and processor.threadable:
            slice_size = max(self.min_slice_size, int(len(pages) / self.max_slices))
            page_slices = [pages[i*slice_size:(i*slice_size)+slice_size] for i in range(int(len(pages)/slice_size))]
            if len(pages) % slice_size != 0:
                page_slices.append(pages[len(page_slices)*slice_size:])
        else:
            page_slices = [pages]

        self.logger.debug(f"Page slices={page_slices}")

        proc = processor(self.logger, **processor_args)
        data_slices = self.slice_data(data, page_slices, proc.requirements())
        thread_args = [{
            'processor':processor, 
            'processor_args': {
                'logger':self.logger, **processor_args
            } ,
            'data': ds
        } for ds in data_slices]

        if len(page_slices) > 1:
            with mp.Pool(self.max_threads if (self.max_threads and self.max_threads > 1) else None) as p:
                sliced_results = p.map(Burdoc._process_slice, thread_args, chunksize=1)
        else:
            sliced_results = [Burdoc._process_slice(thread_args[0])]

        self.merge_data(data, sliced_results, proc.generates())

    def read(self, path: os.PathLike, pages: Optional[List[int]]=None) -> Any:
        
        pdf = fitz.open(path)
        if not pages:
            pages = np.arange(0, pdf.page_count, dtype=np.int16)
        else:
            pages = [p for p in pages if p < pdf.page_count]
        pdf.close()

        data = {'metadata':{'path':path}}
        renderers = []

        for p,args,render_p in self.processors:
            self.run_processor(p, args, pages, data)
            if render_p:
                renderers.append(p(self.logger, **args))

        if self.render:
            render_pages(self.logger, data, renderers)

        return {k:data[k] for k in self.return_fields}






