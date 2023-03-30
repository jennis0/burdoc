# Getting Started

Here's how to quickly get started with applying Burdoc to your files.

```{toctree}
  :hidden:
  :maxdepth: 1
```

```{contents}
    :depth: 1
    :local:
    :backlinks: top

```

## Prerequisites
Burdoc requries the following libraries to be installed.

* [Python >= 3.8](https://www.python.org/downloads/)

### ML Prerequisites
The transformer-based table detection use by Burdoc by default can be quite slow on CPU, often taking several seconds per page, you'll see a large performance increase by running it on a GPU. To avoid messing around with package versions after the fact, it's generally better to install GPU drivers and GPU accelerated versions of PyTorch first if available.

* [Cuda](https://developer.nvidia.com/cuda-downloads)
* [PyTorch](https://pytorch.org/get-started/locally/)


## Installation

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

### Developer Install
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

### Command Line
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
### Library

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