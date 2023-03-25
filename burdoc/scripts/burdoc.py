import argparse
import json
import logging
import os

from typing import List

from ..burdoc_parser import BurdocParser

def parse_range(text_range: str) -> List[int]:
    numbers = []
    comma_parts = text_range.split(",")
    print(text_range)
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
            

    

def run():
    """Run the BurdocParser in the command line
    """
    argparser = argparse.ArgumentParser()

    argparser.add_argument("file", type=str, help="Path to the PDF file you want to prase")
    argparser.add_argument('outfile', type=str, help="Path to file to write output to", nargs="?")
    argparser.add_argument('--pages', help="List of pages to process. Accept comma separated list, specify ranged with '-'", required=False, default=None)
    argparser.add_argument('--mltables', action='store_true', required=False, default=False, help="Use ML table finding. Warning, this can be slow without GPU acceleration")
    argparser.add_argument('--images', action='store_true', required=False, default=False, help="Extract images from PDF and store in output. This can lead to very large output JSON files.")
    argparser.add_argument("--single-threaded", action="store_true", required=False, default=False, help="Force Burdoc to run in single-threaded mode")
    argparser.add_argument("--performance", action="store_true", help="Dump timing infor at end of processing", default=False)
    argparser.add_argument("--debug", action="store_true", help="Dump debug messages to log")
    args = argparser.parse_args()

    if args.pages:
        pages = parse_range(args.pages)
    else:
        pages = None

    parser = BurdocParser(
        use_ml_table_finding=args.mltables,
        extract_images=args.images,
        max_threads=1 if args.single_threaded else None,
        print_performance=args.performance,
        log_level = logging.DEBUG if args.debug else logging.WARNING
    )

    if os.path.exists(args.file):
        print(f"Parsing {args.file}")
        out = parser.read(args.file, pages=pages)

        if not args.outfile:
            if ".pdf" in args.file:
                outfile = args.file.replace(".pdf", ".json")
            else:
                outfile = str(args.file) + ".json"
        else:
            outfile = args.outfile

        print(f"Writing output to {outfile}")
        with open(outfile, 'w', encoding='utf-8') as file_handle:
            json.dump(out, file_handle)
    else:
        raise FileNotFoundError(args.file)