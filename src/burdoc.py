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

from .utils.render_pages import render_pages

class Burdoc(object):

    def __init__(self, log_level: int=logging.INFO):
        self.log_level = log_level

        logger_tt.setup_logging(
            log_path="burdoc.log", suppress_level_below=log_level,
            full_context=2,
            use_multiprocessing=True, suppress=['logger_tt', 'pytorch', 'timm', 'PIL']
        )
        self.logger = logger_tt.getLogger('burdoc')
        self.min_slice_size = 4
        self.max_slices = 20
        self.max_threads = None

        self.mlTableProcessor = MLTableProcessor(self.logger)


    @staticmethod
    def _process_slice(arg_dict: Any) -> Dict[str, Any]:
        pa = arg_dict['processor_args']
        processor = arg_dict['processor'](**pa)
        processor.process(arg_dict['data'])
        return arg_dict['data']

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
        

    def run_mp_processor(self, processor: Processor, pages: List[int], data: Dict[str, Any]) -> Dict[str, Any]:
        if len(pages) > 1 and (not self.max_threads or self.max_threads > 1):
            slice_size = max(self.min_slice_size, int(len(pages) / self.max_slices))
            page_slices = [pages[i*slice_size:(i*slice_size)+slice_size] for i in range(int(len(pages)/slice_size))]
            if len(pages) % slice_size != 0:
                page_slices.append(pages[len(page_slices)*slice_size:])
        else:
            page_slices = [pages]

        self.logger.debug(f"Page slices={page_slices}")

        data_slices = self.slice_data(data, page_slices, processor.requirements())
        thread_args = [{
            'processor':processor, 
            'processor_args': {
                'logger':self.logger, 
            },
            'data': ds
        } for ds in data_slices]

        if len(page_slices) > 1:
            with mp.Pool(self.max_threads if (self.max_threads and self.max_threads > 1) else None) as p:
                sliced_results = p.map(Burdoc._process_slice, thread_args, chunksize=1)
        else:
            sliced_results = [Burdoc._process_slice(thread_args[0])]

        self.merge_data(data, sliced_results, processor.generates())

    def read(self, path: os.PathLike, pages: Optional[List[int]]=None) -> Any:
        
        if not pages:
            pdf = fitz.open(path)
            pages = np.arange(0, pdf.page_count, dtype=np.int16)
            pdf.close()

        data = {'metadata':{'path':path}}

        self.run_mp_processor(PDFLoadProcessor, pages, data)
        self.mlTableProcessor.process(data)
        self.run_mp_processor(MarginProcessor, pages, data)
        self.run_mp_processor(LayoutProcessor, pages, data)
        #render_pages(self.logger, data, [PDFLoadProcessor, type(self.mlTableProcessor), LayoutProcessor], pages)
        self.run_mp_processor(ReadingOrderProcessor, pages, data)
        render_pages(self.logger, data, [MarginProcessor, ReadingOrderProcessor], pages)

        return data






