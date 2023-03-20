from logging import Logger

from .processor import Processor

class Processor(Processor):

    def __init__(self, name: str, logger: Logger):
        super().__init__(name, logger)
        self.max_threads = None