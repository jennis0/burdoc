import pytest

from burdoc.elements import LayoutElement, LayoutElementGroup, Bbox

@pytest.fixture
def layout_element():
    return LayoutElement(Bbox(70., 40., 100., 50., 200., 300.))

class TestLayoutElement():
    
    def test_unique_id(self, bbox):
        e1 = LayoutElement(bbox)
        e2 = LayoutElement(bbox)
        assert e1.element_id != e2.element_id
        
    def test_str_rep(self, bbox):
        element = LayoutElement(bbox)
        element.element_id = "aaaaaaaa"
        assert element._str_rep() == f"<LayoutElement Id=aaaaaaaa... Bbox={str(bbox)}>"
        
    def test_str_rep_with_extras(self, bbox):
        element = LayoutElement(bbox)
        element.element_id = "aaaaaaaa"
        extras = {'Test':'test'}
        assert element._str_rep(extras=extras) == f"<LayoutElement Id=aaaaaaaa... Bbox={str(bbox)} Test=test>"
        
    @pytest.mark.parametrize('use_bbox', [True, False], ids=['with_bbox', 'no_bbox'])
    @pytest.mark.parametrize('extras', [None, {'Test':'test'}], ids=['with_extras', 'no_extras'])
    def test_to_json(self, bbox, use_bbox, extras):
        expected = {
            'name':'layoutelement',
        }
        if use_bbox:
            expected['bbox'] = bbox.to_json()
        if extras:
            for key, val in extras.items():
                expected[key] = val
                
        element = LayoutElement(bbox)
        assert element.to_json(extras=extras, include_bbox=use_bbox) == expected
        
        
class TestLayoutElementGroup():

    def test_bbox_init(self, bbox):
        leg = LayoutElementGroup(bbox=bbox)
        
    def test_item_init(self, line):
        leg = LayoutElementGroup(items=[line])
    
    
    def test_no_item_bbox_init(self):
        with pytest.raises(TypeError):
            leg = LayoutElementGroup()
        
    
    def test_append(self, bbox, line):
        leg = LayoutElementGroup(bbox)
        leg.append(line)
        assert len(leg.items) == 1
        assert leg.items[0] == line
        
    def test_append_no_bbox_update(self, line, layout_element):
                
        leg1 = LayoutElementGroup(items=[line])
        leg1.append(layout_element, update_bbox=False)
        assert len(leg1.items) == 2
        assert leg1.bbox == line.bbox
        
    def test_remove(self, bbox, line):
        leg = LayoutElementGroup(bbox, items=[line])
        leg.remove(line)
        assert len(leg.items) == 0
        
    def test_remove_no_bbox_update(self, bbox, line, layout_element):
        leg = LayoutElementGroup(bbox, items=[line, layout_element])
        test_bbox = leg.bbox.clone()
        leg.remove(line, update_bbox=False)
        assert leg.bbox == test_bbox
        
    def test_merge(self, line, layout_element):
                
        leg1 = LayoutElementGroup(items=[line])
        leg2 = LayoutElementGroup(items=[layout_element])
        leg1.merge(leg2)
        assert len(leg1.items) == 2
        assert leg1.items[0] == layout_element
                
    def test_iterable(self, line, layout_element):
        items=[line, layout_element]
        leg = LayoutElementGroup(items = items)
        count = 0
        for i1,i2 in zip(items, leg):
            assert i1 == i2
            count += 1
        assert count == 2
        
    def test_to_json(self, layout_element):
        expected = {
            'name':'layoutelementgroup',
            'items':[layout_element.to_json()]
        }
        leg = LayoutElementGroup(items=[layout_element])
        assert leg.to_json() == expected
        
        expected['bbox'] = leg.bbox.to_json()
        assert leg.to_json(include_bbox=True) == expected
        