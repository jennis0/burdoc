import burdoc.processors.table_processors
from burdoc.burdoc_parser import BurdocParser

class TestBurdocParser():
        
    def test_init(self):
        _ = BurdocParser()
    
    def test_init_with_ml_tables(self):
        parser = BurdocParser(use_ml_table_finding=True)
        assert parser.processors[1][0] == burdoc.processors.table_processors.MLTableProcessor
        
    def test_init_no_ml_tables(self):
        parser = BurdocParser(use_ml_table_finding=False)
        assert parser.processors[1][0].name != burdoc.processors.table_processors.MLTableProcessor