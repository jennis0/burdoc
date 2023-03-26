<br/>
<p align="center">
  <!-- <a href="https://github.com/jennis0/burdoc">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a> -->

  <h1 align="center">Burdoc: Advanced PDF Parser</h1>
  <p align="center">
A python library for parsing structured text, images, and tables from PDFs.
  </p>
</p>

<div align="center">

<a href="">![Downloads](https://img.shields.io/github/downloads/jennis0/Burdoc/total)</a> 
<a href="">![Contributors](https://img.shields.io/github/contributors/jennis0/burdoc?color=dark-green)</a>
<a href="">![Issues](https://img.shields.io/github/issues/jennis0/burdoc)</a>
<a href="">![License](https://img.shields.io/github/license/jennis0/burdoc)</a>

</div>

## Table Of Contents

- [Table Of Contents](#table-of-contents)
- [About the Project](#about-the-project)
    - [Why Another PDF Parsing Library?](#why-another-pdf-parsing-library)
  - [Key Features](#key-features)
  - [Limitations](#limitations)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
    - [Command Line](#command-line)
    - [Library](#library)
- [Roadmap](#roadmap)
- [Built With](#built-with)
- [Contributing](#contributing)
  - [Creating A Pull Request](#creating-a-pull-request)
- [License](#license)
- [Authors](#authors)
- [Acknowledgements](#acknowledgements)

## About the Project

#### Why Another PDF Parsing Library?
Excellent question! Between pdfminer, PyMuPDF, Tika, and many others there are a plethora of tools for parsing PDFs, but nearly all are focused on the initial step of either pulling out raw content. Burdoc's goal is to generate a rich semantic representation of a PDF, including headings, reading order, tables, and images.

### Key Features
 - **Rich Document Representation:** Burdoc is able to identify most common types of text, including lists, headers/footers, asides, and multiple levels of titles.
 - **Complex Reading Order Inference:** Burdoc uses a multi-stage algorithm to infer reading order even in complex pages with changing numbers of columns, split sections, and asides.
 - **ML-Powered Table Extraction:** Burdoc (optionally) makes use of the latest ML models for identifying tables, alongside a rules-based approach to identify inline tables.


### Limitations
 - **OCR:** As Burdoc relies on high-precision font and location information for it's processing it is likely to do spectacularly badly at parsing OCR'd PDFsBurdoc is not suitable for use with OCR'd PDFs.
 - **Right-to-Left Text:** All parsing is for left-to-right languages only.
 - **Complex Figures:** Areas with large amounts of text arranged around figures in a arbitrary fashion will not be extracted correctly.
 - **Forms:** Currently Burdoc has no way to recognise complex forms.

## Getting Started

[Docs](https://jennis0.github.io/burdoc/burdoc.html)

This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.

* Python3
* Cuda11 [Optional] - *ML Table extraction is greatly accelerated by GPUs if available*

### Installation
To install burdoc from pip
```bash
pip install burdoc
```
To build it directly from source
```bash
git clone https://github.com/jennis0/burdoc
cd burdoc
pip install .
```

## Usage
Burdoc can be used as a library or directly from the command line depending on your usecase.

#### Command Line
```bash
burdoc <input-file> [output-file] [--mltables] [--images]

ARGUMENTS:
  <input-file> - Path to input pdf
  [output-file] - Optional path to output location. [default: {input-file}.json]

FLAGS:
  --mltables  - Use packaged ML table detection algorithm (very slow without GPU acceleration). [default: False]
  --images    - Extract images from the PDF. Can cause the output file to be very large. [default: False]
  --single-threaded - By default, Burdoc will split files > 50 pages over multiple threads. Only effects large files. [default: False]
```
#### Library

```python
from burdoc import BurdocParser

parser = BurdocParser(
  use_ml_table_finding: bool=False,    # Use ML table detection
  extract_images:       bool=False,    # Store extracted images
  generate_page_images: bool=False,    # Generate and store images of each PDF page
  max_threads:          Optional[int]=None  # Maximum number of threads to use. Set to None to use default or 1 
                                            # to force single threaded
)
content = parser.read('file.pdf')
```

## Roadmap

See the [open issues](https://github.com/jennis0/burdoc/issues) for a list of proposed features (and known issues).

## Built With

* [PyMuPDF](https://github.com/pymupdf/PyMuPDF)
* [Pillow](https://github.com/python-pillow/Pillow)
* [Huggingface Transformers](https://huggingface.co/)

## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.
* If you have suggestions for adding or removing projects, feel free to [open an issue](https://github.com/jennis0/burdoc/issues/new) to discuss it, or directly create a pull request after you edit the *README.md* file with necessary changes.
* Please make sure you check your spelling and grammar.
* Create individual PR for each suggestion.

### Creating A Pull Request

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See [LICENSE](https://github.com/jennis0/Burdoc/blob/main/LICENSE.md) for more information.

## Authors

* **jennis0** - [Github Profile](https://github.com/jennis0)

## Acknowledgements

* [ShaanCoding](https://github.com/ShaanCoding/) - *ReadME-Generator*
* [ImgShields](https://shields.io/)