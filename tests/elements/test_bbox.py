import pytest

from burdoc.elements.bbox import Bbox, Point

@pytest.fixture
def bbox2():
    return Bbox(75., 75., 125., 150., 200., 300.)

@pytest.fixture
def bbox3():
    return Bbox(50., 25., 100., 125., 200., 300.)

class TestBbox():
    
    def test_x0_norm(self, bbox):
        assert bbox.x0_norm() == 0.25
        
    def test_x1_norm(self, bbox):
        assert bbox.x1_norm() == 0.5

    def test_y0_norm(self, bbox):
        assert bbox.y0_norm() == 0.25
        
    def test_y1_norm(self, bbox):
        assert bbox.y1_norm() == 0.5
            
    def test_height(self, bbox):
        assert bbox.height() == 75.
        
    def test_width(self, bbox):
        assert bbox.width() == 50.
        
    def test_center(self, bbox):
        assert bbox.center() == Point(75., 112.5)
        
    def test_is_vertical_true(self, bbox):
        assert bbox.is_vertical() == True
        
    def test_is_vertical_false(self, bbox):
        bbox.x1 = bbox.x0 + 100
        assert bbox.is_vertical() == False
        
    def test_clone(self, bbox):
        clone = bbox.clone()
        assert clone == bbox
        clone.x0 = bbox.x0 - 10
        assert clone != bbox
        
    @pytest.mark.parametrize('dims', [[50, 75, 25], [101, 125, 0.], [25, 75, 25]])
    def test_x_overlap(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = dims[0]
        offset_bbox.x1 = dims[1]
        assert bbox.x_overlap(offset_bbox) == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 0.5], [101, 125, 0.], [25, 75, 0.5]])
    def test_x_overlap_first_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = dims[0]
        offset_bbox.x1 = dims[1]
        assert bbox.x_overlap(offset_bbox, 'first') == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 1.], [101, 125, 0.], [25, 75, 0.5]])
    def test_x_overlap_second_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = dims[0]
        offset_bbox.x1 = dims[1]
        assert bbox.x_overlap(offset_bbox, 'second') == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 0.5], [25, 125, 0.5], [50, 55, 0.1]])
    def test_x_overlap_max_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = dims[0]
        offset_bbox.x1 = dims[1]
        assert bbox.x_overlap(offset_bbox, 'max') == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 1.], [25, 125, 1.], [45, 55, 0.5]])
    def test_x_overlap_min_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = dims[0]
        offset_bbox.x1 = dims[1]
        assert bbox.x_overlap(offset_bbox, 'min') == dims[2] 

    @pytest.mark.parametrize('dims', [[50, 75, 0.125], [25, 125, 0.25]])
    def test_x_overlap_page_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = dims[0]
        offset_bbox.x1 = dims[1]
        assert bbox.x_overlap(offset_bbox, 'page') == dims[2]
        
    def test_x_overlap_thin(self, bbox):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = 50
        offset_bbox.x1 = 50.2
        assert bbox.x_overlap(offset_bbox, 'second') == 1.

    def test_x_overlap_inf_thin(self, bbox):
        offset_bbox = bbox.clone()
        offset_bbox.x0 = 50
        offset_bbox.x1 = 50.00001
        assert bbox.x_overlap(offset_bbox, 'second') == 0.

    ### Y Overlap ###
    @pytest.mark.parametrize('dims', [[50, 75, 0], [101, 125, 24.], [100, 125, 25]])
    def test_y_overlap(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = dims[0]
        offset_bbox.y1 = dims[1]
        assert bbox.y_overlap(offset_bbox) == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 0.], [50, 112.5, 0.5], [100, 125, 1/3]])
    def test_y_overlap_first_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = dims[0]
        offset_bbox.y1 = dims[1]
        assert bbox.y_overlap(offset_bbox, 'first') == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 0.], [100, 125, 1.], [25, 100, 1/3]])
    def test_y_overlap_second_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = dims[0]
        offset_bbox.y1 = dims[1]
        assert bbox.y_overlap(offset_bbox, 'second') == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 0.], [25, 125, 0.5], [75, 100, 1/3]])
    def test_y_overlap_max_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = dims[0]
        offset_bbox.y1 = dims[1]
        assert bbox.y_overlap(offset_bbox, 'max') == dims[2]
        
    @pytest.mark.parametrize('dims', [[50, 75, 0.], [25, 125, 2/3], [80, 85, 1.0]])
    def test_y_overlap_min_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = dims[0]
        offset_bbox.y1 = dims[1]
        assert bbox.y_overlap(offset_bbox, 'min') == dims[2] 

    @pytest.mark.parametrize('dims', [[75, 105, 0.1], [0, 150, 0.25]])
    def test_y_overlap_page_norm(self, bbox, dims):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = dims[0]
        offset_bbox.y1 = dims[1]
        assert bbox.y_overlap(offset_bbox, 'page') == dims[2]
        
    def test_y_overlap_thin(self, bbox):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = 90
        offset_bbox.y1 = 90.2
        assert bbox.y_overlap(offset_bbox, 'second') == 1.

    def test_y_overlap_inf_thin(self, bbox):
        offset_bbox = bbox.clone()
        offset_bbox.y0 = 90
        offset_bbox.y1 = 90.0001
        assert bbox.y_overlap(offset_bbox, 'second') == 0.
        
        
    def test_overlap(self, bbox, bbox2):
        bbox2.x1 -= 10
        assert bbox.overlap(bbox2) == 1875.
        assert bbox.overlap(bbox2, "first") == 0.5
        assert bbox.overlap(bbox2, "second") == 0.625
        assert bbox.overlap(bbox2, "min") == 0.625
        assert bbox.overlap(bbox2, "max") == 0.5
        
    def test_x_distance(self, bbox, bbox2, bbox3):
        assert bbox.x_distance(bbox2) == 25.
        assert bbox2.x_distance(bbox) == -25.
        assert bbox.x_distance(bbox3) == 0.
        
    def test_y_distance(self, bbox, bbox2, bbox3):
        assert bbox.y_distance(bbox3) == -37.5
        assert bbox3.y_distance(bbox) == 37.5
        assert bbox.y_distance(bbox2) == 0.
        
    def test_from_points(self, bbox):
        p0 = Point(bbox.x0, bbox.y0)
        p1 = Point(bbox.x1, bbox.y1)
        assert Bbox.from_points(p0, p1, bbox.page_width, bbox.page_height) == bbox
        
    def test_merge(self, bbox, bbox2):
        expected_bbox = Bbox(50., 75., 125., 150., 200., 300.)
        assert Bbox.merge([bbox, bbox2]) == expected_bbox

    def test_merge_fail_on_empty(self):
        with pytest.raises(ValueError):
            Bbox.merge([])

    def test_to_json(self, bbox):
        expected_json = {
            'x0':50., 'y0':75., 'x1':100., 'y1':150.
        }
        assert bbox.to_json() == expected_json
        
    def test_to_json_with_include_page(self, bbox):
        expected_json = {
            'x0':50., 'y0':75., 'x1':100., 'y1':150., 'pw':200., 'ph':300.
        }
        assert bbox.to_json(include_page=True) == expected_json