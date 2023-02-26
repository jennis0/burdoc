import logging
import abc
from plotly.graph_objects import Figure

from typing import Any, List, Dict, Optional

class Processor(abc.ABC):

    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self.logger = logger
        
    @abc.abstractstaticmethod
    def requirements() -> List[str]:
        '''Return list of required data fields'''
        pass

    @abc.abstractstaticmethod
    def generates(self) -> List[str]:
        '''Return list of fields added by this processor'''
        pass

    @abc.abstractmethod
    def process(self, data: Any) -> Any:
        '''Transforms the processed data'''
        pass

    def get_page_data(self, data: Any, page_number: Optional[int]=None) -> Any:
        reqs = self.requirements()
        if page_number:
            pages = [page_number]
        else:
            pages = list(data[reqs[0]].keys())
        for pn in pages:
            yield [pn] + [data[r][pn] for r in reqs]
    
    def get_data(self, data: Any):
        return [data[r] for r in self.requirements()]
    
    def check_requirements(self, data: Any):
        for r in self.requirements():
            if r not in data:
                self.logger.error(f"Missing required data field {r}")
                raise Exception
    
    @abc.abstractstaticmethod
    def add_generated_items_to_fig(self, page_number:int, fig: Figure, data: Dict[str, Any]):
        pass
            
