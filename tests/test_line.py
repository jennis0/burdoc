import pytest

from burdoc.elements.line import LineElement

class TestLineElement():
    
    def test_from_dict(self, line):
        bbox_dict = (50., 75., 100., 150.)
        page_width=200.
        page_height=300.
        pymupdf_line = {
            'wmode':0,
            'dir':(1.0,0.0),
            'bbox':bbox_dict,
            'spans':[
                {
                    "size":12,
                    "flags": 0,
                    "font": "Calibri-standard",
                    "color": 0,
                    "origin": (50.0, 100.0),
                    "text": "span text",
                    "bbox": (50.0, 100.0, 100., 150.)
                }    
            ]
        }
        test_line = LineElement.from_dict(pymupdf_line, page_width, page_height)
        test_line.id = line.id
        assert test_line.spans[0].font == line.spans[0].font
        assert test_line.spans == line.spans
        assert test_line.bbox == line.bbox
        assert test_line.rotation == line.rotation
        assert test_line.title == line.title
        #assert line == test_line
        