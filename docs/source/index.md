![Burdoc Logo](_static/Burdoc-1.png)

# Burdoc: Advanced PDF Parsing For Python

```{toctree}
:maxdepth: 1

self
getting_started
output
module/module
```

## About the Project

Burdoc is a python library and script designed to automate the extraction of complex, text-driven content from PDFs. Burdoc generates a rich semantic representation of a PDF, including headings, reading order, tables, and images that can be used for downstream processing.

#### Why Another PDF Parsing Library?
Excellent question! Between pdfminer, PyMuPDF, Tika, and many others there are a plethora of tools for parsing PDFs, but nearly all are focused on the initial step of pulling out raw content, not on representing the documents actual meaning. 

### Key Features
 - **Rich Document Representation:** Burdoc is able to identify most common types of text, including:
   -  Paragraphs
   -  Headings
   -  Lists (ordered and unordered)
   -  Headers, footers and sidebars,
   -  Visual Asides such as read-out boxes

-  **Structured Output:** Burdoc generates a comprehensive JSON representation of the text. Unlike many other tools it preserves information such metadata, fonts, and original bounding boxes to give downstream users as much information as is needed.
   
 - **Complex Reading Order Inference:** Burdoc uses a multi-stage algorithm to infer reading order even in complex pages with changing numbers of columns, split sections, and asides.
  
 - **ML-Powered Table Extraction:** Burdoc makes use of the latest machine learning models for identifying tables, alongside a rules-based approach to identify inline tables.

 - **Large Documents:** By relying on PyMuPDF rather than pdfminer, the core PDF reading task is substantially faster than other libraries, and can handle large files (~1000s of pages or 100s of Mbs in size) with ease. Running a single page through Burdoc can be quite slow due to expensive initialisation requirements and takes O(2s) but with GPU acceleration and multithreading support we can process documents at 0.2-0.5s/page




### Limitations
 - **OCR:** As Burdoc relies on high-precision font and location information for it's processing it is likely to perform badly when parsing OCR'd files. 
 - **Right-to-Left Text:** All parsing is for left-to-right languages only.
 - **Complex Figures:** Areas with large amounts of text arranged around figures in a arbitrary fashion will not be extracted correctly.
 - **Forms:** Currently Burdoc has no way to recognise complex forms.



