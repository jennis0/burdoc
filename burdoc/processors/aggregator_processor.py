import logging
from typing import Any, Dict, List, Tuple

from plotly.graph_objects import Figure

from .processor import Processor


class AggregatorProcessor(Processor):

    def __init__(self,
                 processors: List[Processor],
                 processor_args: List[Any],
                 render_processors: List[bool],
                 additional_reqs: List[str],
                 log_level: int=logging.INFO
                ):
        super().__init__("aggregator", log_level=log_level)
        self.processors = [proc(**proc_args, log_level=log_level) for proc,proc_args in zip(processors, processor_args)]
        self.render_processors = render_processors
        self.additional_reqs = additional_reqs

    def initialise(self):
        for p in self.processors:
            p.initialise()

    def requirements(self) -> Tuple[List[str], List[str]]:
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
        gens = set()
        for p in self.processors:
            gens |= set(p.generates())
        return list(gens)

    def process(self, data: Any) -> Any:
        for p in self.processors:
            self.logger.debug(f"----------------------- Running {type(p).__name__} --------------------")
            p.process(data)
        return data

    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        for p,render in zip(self.processors, self.render_processors):
            if render:
                p.add_generated_items_to_fig(page_number, fig, data)