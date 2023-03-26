from typing import Any, Dict
import pytest

from burdoc.elements.line import LineElement
from burdoc.elements.bbox import Bbox

def test_line_from_dict():
    bbox_dict = ()
    pymupdf_line = {
        'wmode':0,
        'dir':(1.0,0.0),
        'bbox':(50.0, 100.0, 100.0, 150.0),
        'spans':[
            {
                "size":12,
                "flags": 0,
                "font": "font",
                "color": 0,
                "origin": (50.0, 100.0),
                "text": "text",
                "bbox": (50.0, 100.0, 100, 150)
            }    
        ]
    }
    