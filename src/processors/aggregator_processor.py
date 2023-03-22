from logging import Logger
from typing import List, Any, Dict
from plotly.graph_objects import Figure

from .processor import Processor

class AggregatorProcessor(Processor):

    def __init__(self, logger: Logger, 
                 processors: List[Processor], 
                 processor_args: List[Any], 
                 render_processors=List[bool],
                 additional_reqs = List[str]):
        super().__init__("Aggregator", logger)
        self.processors = [p(self.logger, **pa) for p,pa in zip(processors, processor_args)]
        self.render_processors = render_processors
        self.additional_reqs = additional_reqs

    def initialise(self):
        for p in self.processors:
            p.initialise()

    def requirements(self) -> List[str]:
        reqs = set()
        gens = set()
        for p in self.processors:
            rs = p.requirements()
            for r in rs:
                if r not in gens:
                    reqs.add(r)
            gens |= set(p.generates())
        return list(reqs) + self.additional_reqs

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