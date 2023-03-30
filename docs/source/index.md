![Burdoc Logo](_static/Burdoc-1.png)

# Burdoc: Advanced PDF Parsing For Python

```{toctree}
:maxdepth: 1

self
getting_started
output
module/module
```

## Why Another PDF Parsing Library?
Excellent question! Between pdfminer, PyMuPDF, Tika, and many others there are a plethora of tools for parsing PDFs, but nearly all are focused on the initial step of pulling out raw content, not on representing the documents actual meaning. Burdoc's goal is to generate a rich semantic representation of a PDF, including headings, reading order, tables, and images that can be used for downstream processing.

## Key Features
 - **Rich Document Representation:** Burdoc is able to identify most common types of text, including:
   -  Paragraphs
   -  Headings
   -  Lists (ordered and unordered)
   -  Headers, footers and sidebars,
   -  Visual Asides such as read-out boxes

-  **Structured Output:** Burdoc generates a comprehensive JSON representation of the text. Unlike many other tools it preserves information such metadata, fonts, and original bounding boxes to give downstream users as much information as is needed.
   
 - **Complex Reading Order Inference:** Burdoc uses a multi-stage algorithm to infer reading order even in complex pages with changing numbers of columns, split sections, and asides.
  
 - **ML-Powered Table Extraction:** Burdoc makes use of the latest machine learning models for identifying tables, alongside a rules-based approach to identify inline tables.




## Limitations
 - **OCR:** As Burdoc relies on high-precision font and location information for it's processing it is likely to perform badly when parsing OCR'd files. 
 - **Right-to-Left Text:** All parsing is for left-to-right languages only.
 - **Complex Figures:** Areas with large amounts of text arranged around figures in a arbitrary fashion will not be extracted correctly.
 - **Forms:** Currently Burdoc has no way to recognise complex forms.



