import pytest
from burdoc.elements import Bbox, LayoutElement
from burdoc.utils.layout_graph import LayoutGraph

@pytest.fixture
def page_bbox():
    return Bbox(0, 0, 200, 300, 200, 300)

@pytest.fixture
def layout_elements(page_bbox):
    a = LayoutElement(Bbox(5, 5, 95, 10, page_bbox.x1, page_bbox.y1))
    b = LayoutElement(Bbox(105, 5, 195, 20, page_bbox.x1, page_bbox.y1))
    c = LayoutElement(Bbox(30, 70, 87, 90, page_bbox.x1, page_bbox.y1))
    d = LayoutElement(Bbox(50, 100, 150, 200, page_bbox.x1, page_bbox.y1 ))
    return [a,b,c,d]

@pytest.fixture
def layout_graph(page_bbox, layout_elements):
    return LayoutGraph(page_bbox, layout_elements)


class TestLayoutGraph():
    
    def test_layout_graph_creation(self, page_bbox, layout_elements):
        lg = LayoutGraph(page_bbox, layout_elements)

        assert len(lg.nodes[0].down) == 2
        assert lg.nodes[1].element == layout_elements[0]
        
    def test_layout_graph_get_node_int(self, layout_graph):
        assert layout_graph.get_node(0) == layout_graph.nodes[0]
        
    def test_layout_graph_get_node_tuple(self, layout_graph):
        assert layout_graph.get_node((0, 11.1)) == layout_graph.nodes[0]
        
    @pytest.mark.parametrize('node_results', [
        [0, [(1,5),(2,5)], [], [], []],
        [1, [(3, 60)], [(0, 5)], [], [(2, 10)]],
        [2, [(4, 80)], [(0,5)], [(1, 10)], []],
        [3, [(4, 10)], [(1, 60)], [], []],
        [4, [], [(3, 10), (2,80)], [], []]
    ])
    def test_layout_graph_result_root(self, layout_graph, node_results):
        i = node_results[0]
        assert layout_graph.nodes[i].down == node_results[1]
        assert layout_graph.nodes[i].up == node_results[2]
        assert layout_graph.nodes[i].left == node_results[3]
        assert layout_graph.nodes[i].right == node_results[4]
        
    @pytest.mark.parametrize('node_results', [
        [0, []],
        [1, [0]], [2, [0, 1]],
        [3, [1,0]], [4, [3, 2, 1, 0]]
    ])
    def test_node_has_ancestor(self, layout_graph, node_results):
        ancestors = []
        for i in range(5):
            if i == node_results[0]:
                continue
            if layout_graph.node_has_ancestor(node_results[0], i):
                ancestors.append(i)
        assert set(ancestors) == set(node_results[1])
        
    def test_str(self, layout_graph):
        lg_str =\
"""==============================
------------------------------
<N:0 element:ment Id=6e1d1fb8... >
U: 
L: 
R: 
D: (<N:1 element:ment Id=c43ab6cf... >,5),
   (<N:2 element:ment Id=a348264b... >,5)
------------------------------
<N:1 element:ment Id=c43ab6cf... >
U: (<N:0 element:ment Id=6e1d1fb8... >,5)
L: 
R: (<N:2 element:ment Id=a348264b... >,10)
D: (<N:3 element:ment Id=d6e12bce... >,60)
------------------------------
<N:2 element:ment Id=a348264b... >
U: (<N:0 element:ment Id=6e1d1fb8... >,5)
L: (<N:1 element:ment Id=c43ab6cf... >,10)
R: 
D: (<N:4 element:ment Id=de3302ce... >,80)
------------------------------
<N:3 element:ment Id=d6e12bce... >
U: (<N:1 element:ment Id=c43ab6cf... >,60)
L: 
R: 
D: (<N:4 element:ment Id=de3302ce... >,10)
------------------------------
<N:4 element:ment Id=de3302ce... >
U: (<N:3 element:ment Id=d6e12bce... >,10),
   (<N:2 element:ment Id=a348264b... >,80)
L: 
R: 
D: 
=============================="""

        #Can't compare direct values as IDs change...
        assert len(str(layout_graph)) == len(lg_str)
        