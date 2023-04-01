import pytest

from burdoc.elements.font import Font

@pytest.mark.parametrize('font', [
    ['Fontname', 'Fontname', 14.0, 0, False, False, False, False],
    ['Fontname-Semibold', 'Fontname', 14.0, 0, True, False, False, False],
    ['Fontname-SC700', 'Fontname', 12.0, 0, False, False, False, True],
    ['Fontname-Italic', 'Fontname', 10.0, 7000, False, True, False, False],
    ['Fontname-Bold-SC700', 'Fontname', 15.0, 0, True, False, False, True],
    ['FontnameSC-Semiitalic', 'FontnameSC', 12.0, 0, False, True, False, True]
])
def test_font_from_dict(font):
    pymupdf_span = {
        "size": font[2],
        "flags": 16*font[4] + 2*font[5] + 1*font[6],
        "font": font[0],
        "color": font[3],
        "origin": (50.0, 100.0),
        "text": "A test sentence about some thing",
        "bbox": (50.0, 100.0, 100.0, 150.0)
    }
        
    expected_font = Font(*font)
    font = Font.from_dict(pymupdf_span)
    assert font == expected_font


@pytest.mark.parametrize('font', [
    ['Fontname', 'Fontname', 14.0, 0, False, False, False, False],
    ['Fontname-Semibold', 'Fontname', 14.0, 0, True, False, False, False],
    ['Fontname-SC700', 'Fontname', 12.0, 0, False, False, False, True],
    ['Fontname-Italic', 'Fontname', 10.0, 7000, False, True, False, False],
    ['Fontname-Bold-SC700', 'Fontname', 15.0, 0, True, False, False, True],
    ['FontnameSC-Semiitalic', 'FontnameSC', 12.0, 0, False, True, False, True]

])
def test_span_to_json(font):

    burdoc_font = Font(*font)
        
    burdoc_font_json = {
        'name': 'font',
        'font': font[0],
        'family': font[1],
        'size': font[2],
        'colour': font[3],
        'bd': font[4],
        'it': font[5],
        'sp': font[6],
        'sc': font[7]
    }

    assert burdoc_font.to_json() == burdoc_font_json
