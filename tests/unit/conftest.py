import pytest

from burdoc.elements import Bbox, Span, Font, LineElement

@pytest.fixture
def bbox():
    return Bbox(50., 75., 100., 150., 200., 300.)

@pytest.fixture
def font():
    return Font('Calibri-standard', 'Calibri', 12, 0, False, False, False, False)

@pytest.fixture
def span(font, bbox):
    return Span(bbox=bbox, font=font, text="span text")

@pytest.fixture
def line(bbox, span):
    return LineElement(bbox=bbox, spans=[span], rotation=(1.,0.))