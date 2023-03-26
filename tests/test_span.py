import pytest

from burdoc.elements.font import Font
from burdoc.elements.span import Span


@pytest.mark.parametrize('text', ['a test sentence'], ids=['text'])
@pytest.mark.parametrize('size', [9, 9.9], ids=['int size', 'float size'])
@pytest.mark.parametrize('fontname', ['Fontname'], ids=['font'])
@pytest.mark.parametrize('colour', [0, 11311], ids=['black','colour'])
@pytest.mark.parametrize('bold', [False, True], ids=['b','!b'])
@pytest.mark.parametrize('italic', [False, True], ids=['i','!i'])
@pytest.mark.parametrize('superscript', [False, True], ids=['s','!s'])
def test_span_from_dict(text, size, fontname, colour, bold, italic, superscript):
    pymupdf_span = {
        "size":size,
        "flags": 16*bold + 2*italic + 1*superscript,
        "font": fontname,
        "color": colour,
        "origin": (50.0, 100.0),
        "text": text,
        "bbox": (50.0, 100.0, 100, 150)
    }
    
    burdoc_span = Span(Font(fontname, fontname, size, colour, bold, italic, superscript), text)
    assert Span.from_dict(pymupdf_span) == burdoc_span


@pytest.mark.parametrize('text', ['a test sentence'], ids=['text'])
@pytest.mark.parametrize('size', [9, 9.9], ids=['int size', 'float size'])
@pytest.mark.parametrize('fontname', ['Fontname'], ids=['font'])
@pytest.mark.parametrize('colour', [0, 11311], ids=['black','colour'])
@pytest.mark.parametrize('bold', [False, True], ids=['b','!b'])
@pytest.mark.parametrize('italic', [False, True], ids=['i','!i'])
@pytest.mark.parametrize('superscript', [False, True], ids=['s','!s'])
def test_span_to_json(text, size, fontname, colour, bold, italic, superscript):
    
    burdoc_span = Span(Font(fontname, fontname, size, colour, bold, italic, superscript), text)
    burdoc_span_json = {
        'type':'span',
        'text':text,
        'font':{
            'type':'font',
            'font':fontname,
            'family':fontname,
            'size':size,
            'colour':colour,
            'bold':bold,
            'italic':italic,
            'superscript':superscript
        }
    }
    
    assert burdoc_span.to_json() == burdoc_span_json
    