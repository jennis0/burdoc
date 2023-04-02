import burdoc.processors.table_processors
from burdoc.burdoc_parser import BurdocParser
from copy import deepcopy

import pytest

@pytest.fixture
def burdoc_parser():
    return BurdocParser()

class TestBurdocParser():
        
    def test_init(self, burdoc_parser):
        assert isinstance(burdoc_parser, BurdocParser)
    
    def test_init_with_ml_tables(self, burdoc_parser):
        assert burdoc_parser.processors[1][0] == burdoc.processors.table_processors.MLTableProcessor
        
    def test_init_no_ml_tables(self):
        burdoc_parser = BurdocParser(skip_ml_table_finding=True)
        assert burdoc_parser.processors[1][0].name != burdoc.processors.table_processors.MLTableProcessor
        
    def test_init_no_images(self):
        burdoc_parser = BurdocParser(ignore_images=True)
        assert burdoc_parser.processors[0][0](**burdoc_parser.processors[0][1]).ignore_images == True
        
    @pytest.mark.parametrize('slices', [
        [[0],[1],[2],[3]],
        [[0,1],[2,3]],
        [[0,1,2,3]],
    ])
    @pytest.mark.parametrize('requirements', [
        [['a'],[]], [['a','b','c'],[]], [['a'],['d']], [['a'], ['b']]
    ], ids=['one', 'all', 'opt-missing', 'opt-present'])
    def test_slice_data(self, burdoc_parser, slices, requirements):
        data = {
            'metadata': {},
            'a': {0:[], 1:[], 2:[], 3:[]},
            'b': {0:[], 1:[], 2:[], 3:[]},
            'c': {0:[], 1:[], 2:[], 3:[]},
            'performance': {'test':{}}
        }
        
        sliced_data = burdoc_parser._slice_data(data, slices, requirements, 'test')

        for data_slice, slice in zip(sliced_data, slices):
            assert data_slice['slice'] == slice
            if len(requirements[1]) > 0 and requirements[1][0] in data:
                assert set(data_slice.keys()) == \
                    set(['metadata', 'slice', 'performance'] + requirements[0] + requirements[1])
            
            else:
                assert set(data_slice.keys()) == \
                    set(['metadata', 'slice', 'performance'] + requirements[0])
                  
    @pytest.mark.parametrize('slices', [
        [[0],[1],[2],[3]],
        [[0,1],[2,3]],
        [[0,1,2,3]],
    ])
    @pytest.mark.parametrize('requirements', [
        [['a'],[]], [['a','b','c'],[]], [['a'],['d']], [['a'], ['b']]
    ], ids=['one', 'all', 'opt-missing', 'opt-present'])  
    def test_merge_data(self, burdoc_parser, slices, requirements):
        data = {
            'metadata': {},
            'a': {0:[], 1:[], 2:[], 3:[]},
            'b': {0:[], 1:[], 2:[], 3:[]},
            'c': {0:[], 1:[], 2:[], 3:[]},
            'performance': {'test':{}}
        }
        
        sliced_data = burdoc_parser._slice_data(data, slices, requirements, 'test')
        
        for i,s in enumerate(sliced_data):
            #Copy the dictionary - simulates getting new data back from thread
            sliced_data[i] = deepcopy(s)
            s = sliced_data[i]
            
            #Add new data
            s['d'] = {n: [] for n in s['slice']}
            
            #Add performance metric
            s['performance']['test']['measure'] = [0]*len(s['slice'])
        
        merged_data = burdoc_parser._merge_data(data, sliced_data, ['d'], 'test')
                
        assert merged_data == {
            'metadata': {},
            'a': {0:[], 1:[], 2:[], 3:[]},
            'b': {0:[], 1:[], 2:[], 3:[]},
            'c': {0:[], 1:[], 2:[], 3:[]},
            'd': {0:[], 1:[], 2:[], 3:[]},
            'performance': {'test':{'measure':[0,0,0,0]}}
        }
        
        