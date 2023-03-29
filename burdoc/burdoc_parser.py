import logging
import multiprocessing as mp
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import fitz

from .processors import (AggregatorProcessor, ContentProcessor,
                         JSONOutProcessor, LayoutProcessor, MarginProcessor,
                         MLTableProcessor, PDFLoadProcessor, Processor,
                         ReadingOrderProcessor, RulesTableProcessor)
from .utils.logging import get_logger
from .utils.render_pages import render_pages


class BurdocParser(object):
    """Top-level class to extract structured content from PDF.
    
    Example Usage:
    ```python
    from burdoc import BurdocParser
    content = BurdocParser.read("file.pdf")
    ```
    """
 
    def __init__(self,
                 use_ml_table_finding: Optional[bool]=True,
                 max_threads: Optional[int]=None,
                 log_level: int=logging.INFO,
                 show_pages: bool=False,
        ):
        """Instantiate a BurdocParser

        Args:
            use_ml_table_finding (bool, optional): Whether to use ML table finding algorithms. 
                Defaults to True if transformers library is detected, False otherwise.
            max_threads (Optional[int], optional): Maximum number of threads to run. Set to None
                to use default system limits or 1 to force single-threaded mode. Defaults to None.
            log_level (int, optional): Defaults to logging.INFO.
            show_pages (bool, optional): Draw each page as it's extracted with extraction information
                laid on top. Primarily for debugging. Defaults to False.

        Raises:
            ImportError: transformer library detected but loading transformer library failed.
        """                
        self.performance: Dict[str, float] = {}
        self.profile_info: Optional[List[Dict[str, Any]]] = None
        start = time.perf_counter()
        
        self.log_level = log_level
        self.logger = get_logger("burdoc_parser", log_level=log_level)
        self.min_slice_size = 5
        self.max_slices = 12
        self.max_threads = max_threads
        self.show_pages = show_pages
        self.default_return_fields = ['metadata', 'content']
        
        self.processors: List[Tuple[Type[Processor], Dict, bool]] = [
           (PDFLoadProcessor, {}, False),
        ]
        
        if use_ml_table_finding:
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
            'additional_reqs': ['tables'] if use_ml_table_finding else []
           }, True, )
        )
            
        self.performance['initialise'] = round(time.perf_counter() - start, 3)

    @staticmethod
    def _process_slice(arg_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single processor on the received data.

        Args:
            arg_dict Dict[str, Any]: Dictionary containing anything that needs to be passed to this
                thread for execution. Typically:
                {
                    'processor' Type[Processor]: Type of processor to instatiate
                    'processor_args' Dict[str, Any]: Any arguments that should be passed to the processor
                    'data': Dict[str, Any],
                }

        Returns:
            Dict[str, Any]: Any fields created or modified by the processors
        """
        
        processor_args = arg_dict['processor_args']
        processor = arg_dict['processor'](**processor_args)
        
        #Run expensive initialisation
        start = time.perf_counter()
        processor.initialise()
        arg_dict['data']['performance'][processor.name]['initialise'] = [round(time.perf_counter() - start, 3)]
        #Run procesing
        processor.process(arg_dict['data'])
        
        #Return relevant fields from output dictionary
        return {k:arg_dict['data'][k] for k in ['metadata', 'performance'] + processor.generates()}

    def _slice_data(self, data: Dict[str, Any], page_slices: List[List[int]], 
                   requirements: Tuple[List[str], List[str]], processor_name: str):
        keys = requirements[0] + [k for k in requirements[1] if k in data]
        sliced_data = [
            {   'metadata':data['metadata'], 
                'performance':{processor_name:data['performance'][processor_name]}, 
                'slice': ps
            } | \
            {k:{p:data[k][p] for p in ps} for k in keys}
        for ps in page_slices]
        return sliced_data

    def _merge_data(self, original_data: Dict[str, Any], 
                   sliced_data: List[Dict[str, Any]], 
                   new_fields: List[str],
                   processor_name: str):

        for f in new_fields:
            if f not in original_data:
                original_data[f] = {}

        perfs = original_data['performance']
        for data_slice in sliced_data:
            for k in new_fields:
                original_data[k] |= data_slice[k]
                
            for field in data_slice['performance'][processor_name]:
                if field not in perfs[processor_name]:
                    perfs[processor_name][field] = []
                perfs[processor_name][field] += data_slice['performance'][processor_name][field]
                
        original_data['metadata'] |= sliced_data[0]['metadata']
                
        return original_data 
        
    def _run_processor(self, processor: Type[Processor], processor_args: Dict[str, Any], 
                      pages: List[int], data: Dict[str, Any]):
        
        self.logger.debug("========================= Running %s ===========================", type(processor).__name__)

        start = time.perf_counter()
        if processor.name not in data['performance']:
            data['performance'][processor.name] = {}

        if len(pages) > 1 and (not self.max_threads or self.max_threads > 1) and processor.threadable:
            slice_size = max(self.min_slice_size, int(len(pages) / self.max_slices))
            page_slices = [pages[i*slice_size:(i*slice_size)+slice_size] for i in range(int(len(pages)/slice_size))]
            if len(pages) % slice_size != 0:
                page_slices.append(pages[len(page_slices)*slice_size:])
        else:
            page_slices = [pages]

        self.logger.debug("Page slices=%s", str(page_slices))
        
        proc = processor(**processor_args, log_level=self.log_level)
        data_slices = self._slice_data(data, page_slices, proc.requirements(), processor.name)
        thread_args = [{
            'processor':processor, 
            'processor_args': {
                **processor_args, 'log_level': self.log_level
            } ,
            'data': data_slice
        } for data_slice in data_slices]

        if len(page_slices) > 1:
            with mp.Pool(self.max_threads if (self.max_threads and self.max_threads > 1) else None) as p:
                sliced_results = p.map(BurdocParser._process_slice, thread_args, chunksize=1)
        else:
            sliced_results = [BurdocParser._process_slice(thread_args[0])]

        self._merge_data(data, sliced_results, proc.generates(), processor.name)
        
        data['performance'][processor.name]['total'] = round(time.perf_counter() - start, 3)

    def _format_profile_info(self, profile_info: Dict[str, Dict[str, Union[float, List[float]]]]):
        """Update self.last_performance with performance information

        Args:
            profile_info (Dict[str, Dict[str, Union[float, List[float]]]]): 
                Collected processor performance info
        """
        perf_list = []
        for k in profile_info:
            perf_list.append(
                {'name':k, 'total':profile_info[k]['total']}
            )
            for field in profile_info[k]:
                if field == 'total' or field == 'name':
                    continue
                if isinstance(profile_info[k][field], float):
                    perf_list[-1][field] = profile_info[k][field]
                else:
                    perf_list[-1][field] = round(sum(profile_info[k][field]), 3) #type:ignore
                
        perf_list.sort(key=lambda x: x['total'], reverse=True)
        self.profile_info = perf_list

    def print_profile_info(self):
        """Print performance profile for last run
        """
        
        print("=================================================================")
        print("                            Profile                              ")
        print("-----------------------------------------------------------------")
        if self.profile_info:
            for entry in self.profile_info:
                print(f"{entry['name']}:\tTotal={entry['total']}s\tInit:{entry['initialise']}s")
                for key in entry:
                    if key in ['name','total','initialise']:
                        continue
                    print(f"\t{key}={entry[key]}s")
                print("-----------------------------------------------------------------")
        else:
            print("No profile information")
        print("=================================================================")
                
    def read(self, path: str, 
             pages: Optional[List[int]]=None, 
             extract_images: bool=True,
             extract_page_images: bool=False,
             extract_page_hierarchy: bool=True,
        ) -> Any:
        """Read a PDF and output a structured response

        Args:
            path (str): Path of the pdf to load
            pages (Optional[List[int]], optional): List of pages to extract. Defaults to None.
            extract_images: (bool): Extract images from PDF. This can cause the output to become extremely large.
                Default is False
            extract_page_images: (bool): Extract the page images rendered as part of the processing.
                Default is False
            extract_page_hierarchy: Extract a list of headings and titles. Default is False.
            extract_profile_info: Extract timing profile information for this run

        Raises:
            FileNotFoundError: If the file cannot be found. 
            EmptyFileError: If the file has zero length. Subclass of FileDataError and RuntimeError
            ValueError: If unknown file type is specified. Subclass of RuntimeError
            FileDataError: If the document has an invalid structure for the given type. Subclass of RuntimeError

        Returns:
            Dict[str, Any]: Structured content, has format
            {
                'metadata' (Dict[str, Any]): Any metadata about the file itself
                'content' (Dict[int, List[Any]]):  Ordered content organised per-page
                'page_hierarchy (Dict[int, List[Any]]): Headers found in each page
                'images', (Dict[int, List[PIL.Image.Image]], optional): Images extracted from each page.
                    Only generated if extract_images is True
                'page_images', (Dict[int, PIL.Image.Image], optional): Image rendered for each page.
                    Only generated if generate_page_images is True.
            }
        """
        
        if not os.path.exists(path) or not os.path.isfile(path):
            raise FileNotFoundError(path)
                
        start = time.perf_counter()
        pdf = fitz.open(path)
        if not pages:
            pages = [i for i in range(pdf.page_count)]
        else:
            pages = [int(p) for p in pages if p < pdf.page_count]
        pdf.close()

        data = {'metadata':{'path':path}, 'performance':{'burdoc':self.performance}}
        renderers = []

        for processor, processor_args, render_processor in self.processors:
            self._run_processor(processor, processor_args, pages, data)     
            if render_processor:
                renderers.append(processor(**processor_args, log_level=self.log_level))
    
        self.performance['total'] = round(time.perf_counter() - start, 3)

        if self.show_pages:
            render_pages(data, renderers)
            
        self._format_profile_info(data['performance']) #type:ignore
        
        return_fields = [f for f in self.default_return_fields]
        if extract_images:
            return_fields.append("images")
        
        if extract_page_images:
            return_fields.append("page_images")
            
        if extract_page_hierarchy:
            return_fields.append("page_hierarchy")
            
        return {k:data[k] for k in return_fields}






