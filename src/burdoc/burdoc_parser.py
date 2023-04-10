"""BurdocParser provides the primary interface for extracting PDFs. 
It builds a processing chain, based on user configuration and extracts content."""

import logging
import multiprocessing as mp
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import fitz

from .processors import (AggregatorProcessor, HeadingProcessor,
                         JSONOutProcessor, LayoutProcessor, ListProcessor,
                         MarginProcessor, MLTableProcessor, PDFLoadProcessor,
                         Processor, ReadingOrderProcessor, RulesTableProcessor)
from .utils.logging import get_logger
from .utils.render_pages import render_pages


class BurdocParser():
    """Top-level class to extract structured content from PDF.

    Example Usage:
    ```python
    from burdoc import BurdocParser
    content = BurdocParser.read("file.pdf")
    ```
    """

    def __init__(self,
                 detailed: bool = False,
                 skip_ml_table_finding: bool = False,
                 ignore_images: bool = False,
                 max_threads: Optional[int] = None,
                 log_level: int = logging.INFO,
                 show_pages: bool = False,
                 ):
        """Instantiate a BurdocParser. Note that one of either html_out or json_out must be true

        Args:
            detailed (bool): Include detailed information such as font statistics and 
                bounding boxes in the output
            skip_ml_table_finding (bool): Whether to use ML table finding algorithms. 
            ignore_images (bool): Don't extract any images from the document. Much faster but
                prone to errors if images used as layout elements.
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
        self.ignore_images = ignore_images
        self.detailed = detailed
        self.skip_ml_table_finding = skip_ml_table_finding
        self.logger = get_logger("burdoc_parser", log_level=log_level)
        self.min_slice_size = 5
        self.max_slices = 12
        self.max_threads = max_threads
        self.show_pages = show_pages

        self.default_return_fields = ['metadata', 'content']

        self.processors: List[Tuple[Type[Processor], Dict, bool, Optional[Processor]]] = [
            (PDFLoadProcessor,  {'ignore_images': self.ignore_images}, False, None),
        ]

        if not skip_ml_table_finding:
            self.processors.append(
                (MLTableProcessor, {}, False, None)
            )

        self.processors.append(
            (AggregatorProcessor, {
                'processors': [
                    MarginProcessor,
                    LayoutProcessor,
                    RulesTableProcessor,
                    ReadingOrderProcessor,
                    HeadingProcessor,
                    ListProcessor,
                    JSONOutProcessor
                ],
                'processor_args': {'json-out': {'include_bboxes': detailed}},
                'render_default': True,
                'additional_reqs': ['tables'] if not skip_ml_table_finding else []
            }, True, None)
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
                    'processor_instance' (Processor, optional): An optional instantiated version of the
                        processor that can be passed in single threaded contexts
                    'processor_args' Dict[str, Any]: Any arguments that should be passed to the processor
                    'data': Dict[str, Any],
                }

        Returns:
            Dict[str, Any]: Any fields created or modified by the processors
        """

        # Run expensive initialisation
        start = time.perf_counter()

        if 'processor_instance' in arg_dict:
            processor = arg_dict['processor_instance']
        else:
            processor_args = arg_dict['processor_args']
            processor = arg_dict['processor'](**processor_args)
            processor.initialise()

        arg_dict['data']['performance'][processor.name]['initialise'] = [
            round(time.perf_counter() - start, 3)]
        # Run procesing
        processor.process(arg_dict['data'])

        # Return relevant fields from output dictionary
        return {k: arg_dict['data'][k] for k in ['metadata', 'performance'] + processor.generates()}

    def _slice_data(self, data: Dict[str, Any], page_slices: List[List[int]],
                    requirements: Tuple[List[str], List[str]], processor_name: str) \
            -> List[Dict[str, Any]]:
        """Slices the data dictionary into partial data objects based on processor requirements.

        Args:
            data (Dict[str, Any]): Current data object
            page_slices (List[List[int]]): Each requested slice as a list of page numbers
            requirements (Tuple[List[str], List[str]]): A list of required fields and a list of 
                optional fields while will be None if not present
            processor_name (str): Name of the processor the slice is for.

        Returns:
            List[Dict[str, Any]]: Data object split into requested slices
        """
        # Get keys required for sliced data object
        keys = requirements[0] + [k for k in requirements[1] if k in data]

        # Generate sliced data object
        sliced_data = [
            {'metadata': data['metadata'],
                'performance':{processor_name: data['performance'][processor_name]},
                'slice': ps
             } |
            {k: {p: data[k][p] for p in ps} for k in keys}
            for ps in page_slices]
        return sliced_data

    def _merge_data(self, original_data: Dict[str, Any],
                    sliced_data: List[Dict[str, Any]],
                    new_fields: List[str],
                    processor_name: str) -> Dict[str, Any]:
        """Take a set of partial data objects from multiple threads and merge them back 
        with the original data. Note that only the first slice's metadata will be used.

        Args:
            original_data (Dict[str, Any]): Primary data object
            sliced_data (List[Dict[str, Any]]): Sliced data objects with processor-generated fields
            new_fields (List[str]): Fields to copy from slices back to the primary data object
            processor_name (str): Name of the processor

        Returns:
            Dict[str, Any]: An updated primary data object
        """

        # Add new fields to the data object
        for field in new_fields:
            if field not in original_data:
                original_data[field] = {}

        # Copy new fields back to the data object
        perfs = original_data['performance']
        for data_slice in sliced_data:
            for k in new_fields:
                original_data[k] |= data_slice[k]

            # Copy any new performance fields back to the performance object
            for field in data_slice['performance'][processor_name]:
                if field not in perfs[processor_name]:
                    perfs[processor_name][field] = []
                perfs[processor_name][field] += data_slice['performance'][processor_name][field]

        # Update the metadata - assume this
        original_data['metadata'] |= sliced_data[0]['metadata']

        return original_data

    def _run_processor(self, processor: Type[Processor], processor_args: Dict[str, Any],
                       pages: List[int], primary_data: Dict[str, Any],
                       processor_instance: Optional[Processor] = None):
        """Execute a processor on a set of arguments, reading data from, and writing results to,
        the primary data object. 

        This function handles both single and multi-process execution. Processors are passed by
        type as they will be independently instantiated in each process. 

        Args:
            processor (Type[Processor]): Processor type to instantiate
            processor_args (Dict[str, Any]): Any arguments that should be passed to the processor
            pages (List[int]): List of all page numbers to process
            primary_data (Dict[str, Any]): Primary data object
        """

        self.logger.debug(
            "========================= Running %s ===========================",
            type(processor).__name__
        )

        start = time.perf_counter()
        # Create performance object for this processor. Assumes processor names are unique
        if processor.name not in primary_data['performance']:
            primary_data['performance'][processor.name] = {}

        # Run multithreaded implementation
        if len(pages) > 1 and (not self.max_threads or self.max_threads > 1) and processor.threadable:

            # Calculate page shards
            slice_size = max(self.min_slice_size, int(
                len(pages) / self.max_slices))
            page_slices = [pages[i*slice_size:(i*slice_size)+slice_size]
                           for i in range(int(len(pages)/slice_size))]

            # Correction for when len(pages) is not a multiple of slice size
            if len(pages) % slice_size != 0:
                page_slices.append(pages[len(page_slices)*slice_size:])

            self.logger.debug("Page slices=%s", str(page_slices))

            # Instantiate processor to get requirements data
            processor_instance = processor(**processor_args, log_level=self.log_level)

            # Slice data into shards
            data_slices = self._slice_data(
                primary_data, page_slices, processor_instance.requirements(), processor.name)

            # Create runtime argument for each thread
            thread_args = [{
                'processor': processor,
                'processor_args': {
                    **processor_args, 'log_level': self.log_level
                },
                'data': data_slice
            } for data_slice in data_slices]

            # Execute processors
            if len(page_slices) > 1:
                with mp.Pool(self.max_threads if self.max_threads else None) as process:
                    sliced_results = process.map(
                        BurdocParser._process_slice, thread_args, chunksize=1)
            else:
                sliced_results = [BurdocParser._process_slice(thread_args[0])]

            # Merge results back into primary data object
            self._merge_data(primary_data, sliced_results,
                             processor_instance.generates(), processor.name)

        else:
            # Much simpler single threaded execution
            primary_data['slice'] = pages
            slice_args = {
                'processor_args': processor_args | {'log_level': self.log_level},
                'data': primary_data
            }
            if processor_instance:
                slice_args['processor_instance'] = processor_instance
            else:
                slice_args['processor'] = processor
            primary_data = BurdocParser._process_slice(slice_args)

        primary_data['performance'][processor.name]['total'] = round(
            time.perf_counter() - start, 3)

    def _format_profile_info(self, profile_info: Dict[str, Dict[str, Union[float, List[float]]]]):
        """Update self.last_performance with performance information

        Args:
            profile_info (Dict[str, Dict[str, Union[float, List[float]]]]): 
                Collected processor performance info
        """
        perf_list = []
        for k in profile_info:
            perf_list.append(
                {'name': k, 'total': profile_info[k]['total']}
            )
            for field in profile_info[k]:
                if field in ['total', 'name']:
                    continue
                if isinstance(profile_info[k][field], float):
                    perf_list[-1][field] = profile_info[k][field]
                else:
                    # type:ignore
                    perf_list[-1][field] = round(
                        sum(profile_info[k][field]), 3)

        perf_list.sort(key=lambda x: x['total'], reverse=True)
        self.profile_info = perf_list

    def print_profile_info(self):
        """Print performance profile for last run"""

        print("=================================================================")
        print("                            Profile                              ")
        print("-----------------------------------------------------------------")
        if self.profile_info:
            for entry in self.profile_info:
                print(
                    f"{entry['name']}:\tTotal={entry['total']}s\tInit:{entry['initialise']}s")
                for key in entry:
                    if key in ['name', 'total', 'initialise']:
                        continue
                    print(f"\t{key}={entry[key]}s")
                print(
                    "-----------------------------------------------------------------")
        else:
            print("No profile information")
        print("=================================================================")

    def read(self, path: str,
             pages: Optional[List[int]] = None,
             extract_images: bool = True,
             extract_page_images: bool = False,
             extract_page_hierarchy: bool = True) -> Any:
        """Read a PDF and output a structured response

        Args:
            path (str): Path of the pdf to load
            pages (Optional[List[int]], optional): List of pages to extract. Defaults to None.
            extract_images: (bool): Extract images from PDF. This can cause the output to become extremely large.
                Default is False
            extract_page_images: (bool): Extract the page images rendered as part of the processing.
                Default is False
            extract_page_hierarchy: Extract a list of headings and titles. Default is False.

        Raises:
            FileNotFoundError: If the file cannot be found.
            EmptyFileError: If the file has zero length. Subclass of FileDataError and RuntimeError
            ValueError: If unknown file type is specified. Subclass of RuntimeError
            FileDataError: If the document has an invalid structure for the given type. Subclass of 
                RuntimeError

        Returns:
            Dict[str, Any]: Structured content, has format
            {
                'metadata' (Dict[str, Any]): Any metadata about the file itself
                'content' (Dict[int, List[Any]]):  Ordered content organised per-page
                'page_hierarchy (Dict[int, List[Any]]): Headers found in each page
                'images', (Dict[int, List[PIL.Image.Image]], optional): Images extracted from 
                    each page. Only generated if extract_images is True
                'page_images', (Dict[int, PIL.Image.Image], optional): Image rendered for each page.
                    Only generated if generate_page_images is True.
            }
        """

        if not os.path.exists(path) or not os.path.isfile(path):
            raise FileNotFoundError(path)

        start = time.perf_counter()

        for i, p in enumerate(self.processors):
            if p[0].expensive and (self.max_threads == 1 or not p[0].threadable) and not p[3]:
                self.processors[i] = (*self.processors[i][:3], self.processors[i][0](**self.processors[i][1]))
                self.processors[i][-1].initialise()

        pdf = fitz.open(path)
        if not pages:
            pages = list(range(pdf.page_count))
        else:
            pages = [int(p) for p in pages if p < pdf.page_count]
        pdf.close()

        data = {'metadata': {'path': path},
                'performance': {'burdoc': self.performance}}
        renderers = []

        for processor, processor_args, render_processor, proc_instance in self.processors:
            self._run_processor(processor, processor_args, pages, data, proc_instance)
            if render_processor:
                renderers.append(
                    processor(**processor_args, log_level=self.log_level))

        self.performance['total'] = round(time.perf_counter() - start, 3)

        if self.show_pages:
            print(renderers)
            render_pages(data, renderers)

        self._format_profile_info(data['performance'])  # type:ignore

        return_fields = list(self.default_return_fields)
        if extract_images:
            return_fields.append("images")

        if extract_page_images:
            return_fields.append("page_images")

        if extract_page_hierarchy:
            return_fields.append("page_hierarchy")

        # Move font stats out of metadata block
        if 'font_statistics' in data['metadata']:
            data['font_statistics'] = data['metadata']['font_statistics']
            del data['metadata']['font_statistics']

        if self.detailed:
            return_fields.append('font_statistics')

        return {k: data[k] for k in return_fields}
