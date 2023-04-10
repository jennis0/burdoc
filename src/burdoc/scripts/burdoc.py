import argparse
import json
import logging
import os
from typing import List

from ..burdoc_parser import BurdocParser
from ..utils.json_to_html import JsonHtmlConverter


def parse_range(text_range: str) -> List[int]:
    """Split a passed text argument into a list of integers representing the same
    range.

    Args:
        text_range (str): comma separated list of either integers or 'x-y' ranges.

    Raises:
        TypeError: Pased string could not be interpreted as a type
        ValueError: Range fragment could not be understood

    Returns:
        List[int]: List of integers equivalent to passed ranges
    """
    numbers = []
    comma_parts = text_range.split(",")
    for part in comma_parts:
        vals = part.split("-")

        if len(vals) == 2:
            if not str.isnumeric(vals[0]):
                raise TypeError(f"{vals[0]} is not a page number")
            if not str.isnumeric(vals[1]):
                raise TypeError(f"{vals[1]} is not a page number")

            numbers += [i for i in range(int(vals[0]), int(vals[1])+1)]
            continue

        if len(vals) == 1:
            if not str.isnumeric(vals[0]):
                raise TypeError(f"{vals[0]} is not a page number")
            numbers.append(int(vals[0]))
            continue

        raise ValueError(f"Could not parse range fragment {part}")

    return numbers


def create_argparser() -> argparse.ArgumentParser:
    """Creates a preconfigured argument parser.

    Returns:
        argparse.ArgumentParser: The argument parser
    """

    argparser = argparse.ArgumentParser()

    argparser.add_argument(
        "in_file", type=str,
        help="Path to the PDF file you want to parse"
    )

    argparser.add_argument(
        'out_file', type=str,
        help="Path to file to write output to.\nDefaults to [in-file-stem].json/[in-file-stem].html",
        nargs="?"
    )

    argparser.add_argument(
        '--pages',  type=str,
        help="List of pages to process. Accepts comma separated list and ranges specified with '-'",
        required=False, default=None
    )

    argparser.add_argument(
        '--html', 
        help="Output a simple HTML representation of the document, rather than the JSON content.",
        action='store_true', default=False
    )

    argparser.add_argument(
        '--detailed', 
        help="Include BoundingBoxes and font statistics in the output to aid onward processing",
        action="store_true", default=False
    )

    argparser.add_argument(
        '--no-ml-tables',
        help="Turn off ML table finding.\nDefaults to False.",
        action='store_true', required=False, default=False,
    )

    argparser.add_argument(
        '--images', action='store_true', required=False, default=False,
        help="Extract images from PDF and store in output. This can lead to very large output JSON files." +
        "Default is False"
    )

    argparser.add_argument(
        "--single-threaded", action="store_true", required=False,
        default=False, help="Force Burdoc to run in single-threaded mode. Default to off"
    )

    argparser.add_argument(
        "--profile", action="store_true",
        help="Dump timing information at end of processing", default=False
    )

    argparser.add_argument(
        "--debug", action="store_true",
        help="Dump debug messages to log"
    )

    return argparser


def run():
    """Run the BurdocParser in the command line
    """
    argparser = create_argparser()
    args = argparser.parse_args()

    if args.pages:
        pages = parse_range(args.pages)
    else:
        pages = None

    if args.html and args.detailed:
        print("ERROR: Cannot use both detailed and html flags")

    # Create parser
    parser = BurdocParser(
        detailed=args.detailed,
        skip_ml_table_finding=args.no_ml_tables,
        max_threads=1 if args.single_threaded else None,
        log_level=logging.DEBUG if args.debug else logging.WARNING
    )

    # Check file exists
    if not os.path.exists(args.in_file):
        raise FileNotFoundError(args.in_file)

    print(f"Parsing {args.in_file}")
    out = parser.read(args.in_file, pages=pages, extract_images=args.images)

    # Print profiling information
    if args.profile:
        parser.print_profile_info()

    if not args.out_file:
        ending_stem = '.json' if not args.html else '.html'
        if args.in_file.endswith(".pdf"):
            out_file = ".".join(args.in_file.split(".")) + ending_stem
        else:
            out_file = str(args.in_file) + ending_stem
    else:
        out_file = args.out_file

    print(f"Writing output to {out_file}")
    if args.html:
        converter = JsonHtmlConverter()
        html_output = converter.convert(out, True, True)
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(html_output)

    else:
        with open(out_file, 'w', encoding='utf-8') as file_handle:
            json.dump(out, file_handle)
