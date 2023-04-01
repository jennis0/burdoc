import pytest

from burdoc.elements.bbox import Bbox
from burdoc.elements.font import Font
from burdoc.elements.span import Span


@pytest.fixture
def font():
    return Font('Fontname', 'Fontname', 14.0, 0, False, False, False, False)


@pytest.mark.parametrize('text',
                         ['a test sentence', 'another test sentence',
                             'a unicode \u2022 sentence'],
                         ids=['t1', 't2', 'unicode'])
def test_span_from_dict(text, font):
    pymupdf_span = {
        "size": font.size,
        "flags": 0,
        "font": font.name,
        "color": font.colour,
        "origin": (50.0, 100.0),
        "text": text,
        "bbox": (50.0, 100.0, 100.0, 150.0)
    }
    bbox = Bbox(50.0, 100.0, 100.0, 150.0, 200.0, 300.0)
    burdoc_span = Span(bbox=bbox, font=font, text=text)
    span_from_dict = Span.from_dict(pymupdf_span, 200.0, 300.0)
    span_from_dict.element_id = burdoc_span.element_id
    assert span_from_dict.bbox == burdoc_span.bbox
    assert span_from_dict.font == burdoc_span.font
    assert span_from_dict.title == burdoc_span.title


@pytest.mark.parametrize('text',
                         ['a test sentence', 'another test sentence',
                             'a unicode \u2022 sentence'],
                         ids=['t1', 't2', 'unicode'])
def test_span_to_json(text, font):

    bbox = Bbox(50.0, 100.0, 100.0, 150.0, 200.0, 300.0)

    burdoc_span = Span(bbox=bbox, font=font, text=text)

    burdoc_span_json = {
        'name': 'span',
        'text': text,
        'font': font.to_json()
    }

    assert burdoc_span.to_json() == burdoc_span_json
