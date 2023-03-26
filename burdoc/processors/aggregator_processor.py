import logging
import time
from typing import Any, Dict, List, Tuple, Type

from plotly.graph_objects import Figure

from .processor import Processor


class AggregatorProcessor(Processor):
    """The Aggregator processor is used to combine several processors into a single processing step.
    Best practice is to place any chain of processors within an aggregator when each step in the chain
    runs of the same data and can be run within the same thread. This minimises the overhead of copying
    data between threads. 
    """

    name: str = "aggregator"

    def __init__(self,
                 processors: List[Type[Processor]],
                 processor_args: List[Any],
                 render_processors: List[bool],
                 additional_reqs: List[str],
                 log_level: int=logging.INFO
                ):
        super().__init__(AggregatorProcessor.name, log_level=log_level)
        self.processors = [proc(**proc_args, log_level=log_level) for proc,proc_args in zip(processors, processor_args)]
        self.render_processors = render_processors
        self.additional_reqs = additional_reqs

    def initialise(self):
        """Run initialise for all child processors"""
        for p in self.processors:
            p.initialise()

    def requirements(self) -> Tuple[List[str], List[str]]:
        """Generates a smart superset of fields required by the child procesors.
        
        Note that if a field is generated by an earlier processor if won't be added to the requirements.
        If you want to manually require this field (e.g. as it's initially generated by a non-aggregated 
        processor) you can add it via additional_reqs argument in class instantiation.

        Returns:
            Tuple[List[str], List[str]]: Required and optional fields
        """
        reqs = set()
        opt_reqs = set()
        gens = set()
        for processor in self.processors:
            proc_reqs = processor.requirements()
            for req in proc_reqs[0]:
                if req not in gens:
                    reqs.add(req)
            for req in proc_reqs[1]:
                if req not in gens:
                    opt_reqs.add(req)
                    
            gens |= set(processor.generates())
            
        to_remove: List[str] = []
        for req in opt_reqs:
            if req in reqs:
                to_remove.append(req)
        for req in to_remove:
            opt_reqs.remove(req)
            
        return (list(reqs) + self.additional_reqs, list(opt_reqs))

    def generates(self) -> List[str]:
        """Returns the superset of fields generated by the child processors

        Returns:
            List[str]
        """
        gens = set()
        for p in self.processors:
            gens |= set(p.generates())
        return list(gens)

    def _process(self, data: Any) -> Any:
        for p in self.processors:
            self.logger.debug("----------------------- Running %s --------------------", {type(p).__name__})
            start = time.perf_counter()
            p._process(data) #pylint: disable=protected-access
            data['performance'][self.name][p.name] = [round(time.perf_counter() - start, 3)]
        return data

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        for p,render in zip(self.processors, self.render_processors):
            if render:
                p.add_generated_items_to_fig(page_number, fig, data)