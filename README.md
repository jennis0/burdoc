<br/>
<p align="center">
  <a href="https://github.com/jennis0/burdoc">
    <img src="images/Burdoc-1.png" height="250">
  </a>

  <h1 align="center">Burdoc: Advanced PDF Parsing</h1>
  <p align="center">
A python library for extracting structured text, images, and tables from PDFs with context and reading order.
  </p>
</p>

<div align="center">

<a href="">![Build](https://img.shields.io/github/actions/workflow/status/jennis0/burdoc/python-package.yml)
<a href="">![Downloads](https://img.shields.io/github/downloads/jennis0/Burdoc/total)</a> 
<a href="">![Contributors](https://img.shields.io/github/contributors/jennis0/burdoc?color=dark-green)</a>
<a href="">![Issues](https://img.shields.io/github/issues/jennis0/burdoc)</a>
<a href="">![License](https://img.shields.io/github/license/jennis0/burdoc)</a>
<a href="">[![codecov](https://codecov.io/gh/jennis0/burdoc/branch/main/graph/badge.svg?token=7X7146BQ72)](https://codecov.io/gh/jennis0/burdoc)</a>

</div>

## Table Of Contents

- [Table Of Contents](#table-of-contents)
- [About the Project](#about-the-project)
    - [Why Another PDF Parsing Library?](#why-another-pdf-parsing-library)
  - [Key Features](#key-features)
  - [Limitations](#limitations)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
    - [ML Prerequisites](#ml-prerequisites)
  - [Installation](#installation)
    - [Developer Install](#developer-install)
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
Excellent question! Between pdfminer, PyMuPDF, Tika, and many others there are a plethora of tools for parsing PDFs, but nearly all are focused on the initial step of pulling out raw content, not on representing the documents actual meaning. Burdoc's goal is to generate a rich semantic representation of a PDF, including headings, reading order, tables, and images that can be used for downstream processing.

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

#### ML Prerequisites
The transformer-based table detection use by Burdoc by default can be quite slow on CPU, often taking several seconds per page, you'll see a large performance increase by running it on a GPU. To avoid messing around with package versions after the fact, it's generally better to install GPU drivers and GPU accelerated versions of PyTorch first if available.

* [Cuda](https://developer.nvidia.com/cuda-downloads)
* [PyTorch](https://pytorch.org/get-started/locally/)

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

#### Developer Install
To reproduce the development environment for running builds, tests, etc. use
```bash
pip install burdoc[dev]
```
or 
```bash
git clone https://github.com/jennis0/burdoc
cd burdoc
pip install -e ".[dev]"
```

## Usage
Burdoc can be used as a library or directly from the command line depending on your usecase.

#### Command Line
```
usage: burdoc [-h] [--pages PAGES] [--no-ml-tables] [--images] [--single-threaded] [--profile] [--debug] in_file [out_file]

positional arguments:
  in_file            Path to the PDF file you want to parse
  out_file           Path to file to write output to. Defaults to [in-file-stem].json

optional arguments:
  -h, --help         show this help message and exit
  --pages PAGES      List of pages to process. Accepts comma separated list and ranges specified with '-'
  --no-ml-tables     Turn off ML table finding. Defaults to False.
  --images           Extract images from PDF and store in output. This can lead to very large output JSON files. Default is False
  --single-threaded  Force Burdoc to run in single-threaded mode
  --profile          Dump timing information at end of processing
  --debug            Dump debug messages to log
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
