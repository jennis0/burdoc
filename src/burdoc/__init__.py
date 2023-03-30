"""Burdoc: Advanced PDF parser  

Burdoc uses ML and a set of tuned heuristics to perform advanced document layout analysis on PDFs.

Typical usage example:

::
    from burdoc import BurdocParser

    parser = BurdocParser()
data = parser.read('file.pdf')

"""
from .burdoc_parser import BurdocParser
