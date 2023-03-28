import pytest

from burdoc.processors import Processor

class TestProcessor():
    
    Processor.__abstractmethods__ = set()
    
    @pytest.mark.parametrize('name', ['Test1', 'Test2'])
    @pytest.mark.parametrize('max_threads', [1, 12])
    def test_init(self, name, max_threads):
        #Processor.__abstractmethods__ = set()
        proc = Processor(name, max_threads=max_threads)
        assert proc.name == name
        assert proc.max_threads == max_threads
        
    def test_init_no_threads(self):
        #Processor.__abstractmethods__ = set()
        proc = Processor("Test")
        assert proc.name == "Test"
        assert proc.max_threads == None
                
    def test_process(self):
        #Processor.__abstractmethods__ = set()
        proc = Processor("Test")
        data = {'performance':{}}
        proc.process(data)
        assert len(data['performance']['Test']) == 1
        
    def test_get_page_data(self):
        Processor.requirements = lambda self: (['req'], [])
        proc = Processor('Test')
        data = {'req':{1:[1], 2:[1], 3:[1]}, 'optional':{1:[2], 2:[2], 3:[2]}, 'not':{1:[3], 2:[3], 3:[3]}}
        counts = []
        for parts in proc.get_page_data(data):
            assert parts[0] == len(counts) + 1
            counts.append(len(parts))
        assert counts == [2,2,2]
        
    def test_get_page_data_with_pages(self):
        Processor.requirements = lambda self: (['req'], [])
        proc = Processor('Test')
        data = {'req':{1:[1], 2:[1], 3:[1]}, 'optional':{1:[2], 2:[2], 3:[2]}, 'not':{1:[3], 2:[3], 3:[3]}}
        counts = []
        for parts in proc.get_page_data(data, page_number=1):
            assert parts[0] == len(counts) + 1
            counts.append(len(parts))
        assert counts == [2]

    def test_get_page_data_optional_present(self):
        Processor.requirements = lambda self: (['req'], ['optional'])
        proc = Processor('Test')
        data = {'req':{1:[1], 2:[1], 3:[1]}, 'optional':{1:[2], 2:[2], 3:[2]}, 'not':{1:[3], 2:[3], 3:[3]}}
        counts = []
        for parts in proc.get_page_data(data):
            counts.append(len(parts))
        assert counts == [3,3,3]

    def test_get_page_data_optional_not_present(self):
        Processor.requirements = lambda self: (['req'], ['optional'])
        proc = Processor('Test')
        data = {'req':{1:[1], 2:[1], 3:[1]}, 'not':{1:[3], 2:[3], 3:[3]}}
        counts = []
        for parts in proc.get_page_data(data):
            counts.append(len([p for p in parts if p]))
        assert counts == [2,2,2]
        
    def test_get_data(self):
        Processor.requirements = lambda self: (['req'], ['optional'])
        proc = Processor('Test')
        data = {'req':{1:[1], 2:[1], 3:[1]}, 'optional':{1:[2], 2:[2], 3:[1]}, 'not':{1:[3], 2:[3], 3:[1]}}
        got_data = proc.get_data(data)
        assert len(got_data) == 2
        assert len(got_data[0]) == 3
        
    @pytest.mark.parametrize('params', 
                             [[(['req'], []), {'req':{}}, True],
                              [(['req'], []), {'not_req':{}}, False]]
                             , ids=['pass', 'fail'])
    def test_check_requirements_true(self, params):
        Processor.requirements = lambda self: params[0]
        proc = Processor('Test')
        assert proc.check_requirements(params[1]) == params[2]