# Working with Burdoc Output

```{toctree}
  :maxdepth: 4
```

By default, Burdoc returns a JSON dictionary containing the content extracted from the PDF. It will always contain 'metadata', 'content', and 'page_hierarchy' and may optionally contain extracted images and rendered page images


```{contents}
    :depth: 4
    :local:
    :backlinks: top

```

## Metadata
Any file and content metadata produced during the extraction process

| Field | Type | Description
|-|-|-|
| path | str | Path to the original file |
| title | str | Title of the document, if available in the PDF, otherwise is the file name | 
| pdf_metadata | object | Metadata extracted by PyMuPDF | 
| toc | list | Table of content if stored programmatically within the pdf, otherwise [] |

Example Output:

```python
{
    "metadata": {
        "path": "/path/to/file.pdf" 
        "title": "file.pdf" 
        "pdf_metadata": { 
            "format": "PDF 1.7",
            "title": "",
            "author": "Author",
            "subject": "",
            "keywords": "",
            "creator": "Creator",
            "producer": "Producer",
            "creationDate": "D:20230325084930+00'00'",
            "modDate": "D:20230325084930+00'00'",
            "trapped": "",
            "encryption": null
        }, 
        "toc": [] 
    },
}
```
___

## Content
The content field provides all extracted text, images, and tables indexed by page number and ordered in inferred reading order.

| Field | Type | Description | 
|-|-|-|
| Page Index | List[object] | Page number of following content item. Zero-indexed |

Example:

```python
{
 "content": {
        "0": [ #page number
            {
                "name": "textblock", #content form extracted
                "type": "h2", #subtype of content
                "items": [ #subitems within the content
                    {
                        "name": "line"
                        "spans": [
                            {
                                "name": "span",
                                "text": "A Test Document ",
                                "font": {
                                    "name": "font",
                                    "font": "TimesNewRomanPSMT",
                                    "family": "TimesNewRomanPSMT",
                                    "size": 20.0,
                                    "colour": 0,
                                    "bold": false,
                                    "italic": false,
                                    "superscript": false
                                } #/font
                            } #/span
                        ], #/spans
                    } #/line
                ], #/items
            }, #/textblock
        ] #/end page content
    } #/end content
 }
```
___

### Content Types

#### Aside
HTML: ```<div>```

An aside is a block of content visually separated from the main page, usually via a backing image/fill or by a boxed outline. Asides act as a basic container with any other type of content inside.

| Field | Type | Description | 
|-|-|-|
| name | str | "aside" |
| items | list[Content Object] | List of content items, cannot contain another aside |

Example:
```python
{
    'name': 'aside',
    'items': [
        {
            "name": "textblock", #content form extracted
            "type": "h2", #subtype of content
            "items": [ #subitems within the content
                {
                    "name": "line"
                    "spans": [
                        {
                            "name": "span",
                            "text": "A Test Document ",
                            "font": {
                                "name": "font",
                                "font": "TimesNewRomanPSMT",
                                "family": "TimesNewRomanPSMT",
                                "size": 20.0,
                                "colour": 0,
                                "bold": false,
                                "italic": false,
                                "superscript": false
                            } #/font
                        } #/span
                    ], #/spans
                } #/line
            ], #/items
        }, #/textblock
    ]
}
```

#### Font
This expresses the font information of text

| Field | Type | Description | 
|-|-|-|
| name | str | "font" |
| font | str | Name of the font |
| family | str | Name of the inferred font family | 
| size | float | Font size in pt |
| colour | int | Font colour |
| bold | bool | True if text is bold |
| italic | bool | True if text is italic |
| superscript | bool | True if text is superscript |
| smallcaps | bool | True if font is a smallcaps font |

#### Image
HTML: ```<image>```

The fact of an image being present is always extracted, whether or not the images themselves are stored.

| Field | Type | Description | 
|-|-|-|
| name | str | "image" |
| image_type | str | Category of the image, usually ['primary'] for extracted images
| image | int | Index of image within extracted image list | 

#### Line
HTML: None

A line is a single line of text, which may contain multiple spans with differing font information. The end of a line indicates a line break in the original text, not the end of a semantic sentence.

| Field | Type | Description | 
|-|-|-|
| name | str | "line" |
| spans | list[Span] | List of text spans |

#### Span
HTML: ```<span>```

A span is a grouping of test within a line based on font information

| Field | Type | Description | 
|-|-|-|
| name | str | "span" |
| text | str | The extracted text |
| font | Font | Font information for the span |

#### Table
HTML: ```<table>```

Representation of any tables extracted from the document.

| Field | Type | Description | 
|-|-|-|
| name | str | "table" |
| cells | list[list[list[TextBlock]]] | Extracted cells in row-column-cell nesting. Note cells can contain multiple text blocks. | 
| row_header_index | list[int] | Indexes of any columns that should be treated as row headers. |
| col_header_index | list[int] | Indexes of any rows that should be treated as column headers. |

#### TextBlock
HTML: ```<p>,<h[1-5]>```

A set of lines that has been inferred to be part of the same grouping. Usually represents a paragraph.

| Field | Type | Description | 
|-|-|-|
| name | str | "textblock" |
| type | str | Inferred interpretation of the text. One of ['paragraph', 'h[1-5]', 'emphasis', 'small'] | 
| items | list[Line] | All lines contained within the block. |
| block_text | str | A basic representation of all text within the block with all font information removed. |

#### TextList
HTML: ```<ul>,<ol>```

An ordered or unordered list

| Field | Type | Description | 
|-|-|-|
| name | str | "textlist" |
| ordered | bool | Whether the list is ordered or unordered | 
| items | list[TextListItem] | All items contained within the list|

##### TextListItem
| Field | Type | Description | 
|-|-|-|
| name | str | "textlistitem" |
| label | str | The extract label, can be one of [\u2022, (a), a), a., (1), 1), 1.]| 
| items | list[TextBlock] | All paragraphs contained within this list item. |

___

## Page Hierarchy
The page hierarchy is an inferred table of contents based on headers found within the text. It is indexed by page, similarly to the 'content' field.

| Field | Type | Description | 
|-|-|-|
| page | int | Page index |
| index | Tuple[int, int or None] | The item and sub-item index. Sub-item index is none if the element is not within an aside |
| text | str | Simplified text reprentation of the heading. All font information is removed | 
| size | float | Font size in pt |

___

## Images (``--images`` only)
If extracted using the "--images" flag or 'extract_images' argument, images are stored as a page-indexed list of base64 encoded images. If the images flag is not used, ImageElements will still be present in the extracted content but they won't contain the actual image data.

___

## Font Statistics (``--detailed`` only)
If 'detailed' extraction mode is used then font statistics for the full document will be extracted. This includes information on each font, it's occurences, and it's actual size on the page.