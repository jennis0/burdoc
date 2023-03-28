import pytest
import burdoc.processors.table_processors
from burdoc.burdoc_parser import BurdocParser

class TestBurdocParser():
        
    def test_init(self):
        _ = BurdocParser()
    
    @pytest.mark.skipif(not burdoc.processors.table_processors.LOADED_ML_PROCESSORS, reason="Pytorch not installed")
    def test_init_with_transformers(self):
        burdoc.processors.table_processors.LOADED_ML_PROCESSORS = True
        parser = BurdocParser()
        assert parser.processors[1][0] == burdoc.processors.table_processors.MLTableProcessor
        
    def test_init_no_transformers(self):
        burdoc.processors.table_processors.LOADED_ML_PROCESSORS = False
        parser = BurdocParser()
        assert parser.processors[1][0].name != burdoc.processors.table_processors.MLTableProcessor