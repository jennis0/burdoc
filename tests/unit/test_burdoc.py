import burdoc.burdoc_parser
from burdoc.burdoc_parser import BurdocParser
from burdoc.processors.table_processors.ml_table_processor import MLTableProcessor


class TestBurdocParser():
    
    def test_init(self):
        parser = BurdocParser()
    
    def test_init_with_transformers(self):
        burdoc.burdoc_parser._HAS_TRANSFORMERS = True
        parser = BurdocParser()
        assert parser.processors[1][0] == MLTableProcessor
        
    def test_init_no_transformers(self):
        burdoc.burdoc_parser._HAS_TRANSFORMERS = False
        parser = BurdocParser()
        assert parser.processors[1][0] != MLTableProcessor