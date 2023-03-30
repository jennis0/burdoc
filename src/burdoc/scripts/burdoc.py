import argparse
import json
import logging
import os
from typing import List

from ..burdoc_parser import BurdocParser


def parse_range(text_range: str) -> List[int]:
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
            

    

def run():
    """Run the BurdocParser in the command line
    """
    argparser = argparse.ArgumentParser()

    argparser.add_argument("in_file", type=str, help="Path to the PDF file you want to parse")
    argparser.add_argument('out_file', type=str, help="Path to file to write output to.\nDefaults to [in-file-stem].json", nargs="?")
    argparser.add_argument('--pages',  help="List of pages to process. Accepts comma separated list and ranges specified with '-'", required=False, default=None)
    argparser.add_argument('--no-ml-tables', action='store_true', required=False, default=False, 
                           help="Turn off ML table finding.\nDefaults to False.")
    argparser.add_argument('--images', action='store_true', required=False, default=False, 
                           help="Extract images from PDF and store in output. This can lead to very large output JSON files. Default is False")
    argparser.add_argument("--single-threaded", action="store_true", required=False, default=False, help="Force Burdoc to run in single-threaded mode. Default to off")
    argparser.add_argument("--profile", action="store_true", help="Dump timing information at end of processing", default=False)
    argparser.add_argument("--debug", action="store_true", help="Dump debug messages to log")
    args = argparser.parse_args()

    if args.pages:
        pages = parse_range(args.pages)
    else:
        pages = None

    parser = BurdocParser(
        use_ml_table_finding=not args.disable_ml_table_finding,
        max_threads=1 if args.single_threaded else None,
        log_level = logging.DEBUG if args.debug else logging.WARNING
    )

    if os.path.exists(args.in_file):
        print(f"Parsing {args.in_file}")
        out = parser.read(args.in_file, 
                          pages=pages,
                          extract_images=args.images)
        
        if args.profile:
            parser.print_profile_info()

        if not args.out_file:
            if ".pdf" in args.in_file:
                out_file = args.file.replace(".pdf", ".json")
            else:
                out_file = str(args.in_file) + ".json"
        else:
            out_file = args.out_file

        print(f"Writing output to {out_file}")
        with open(out_file, 'w', encoding='utf-8') as file_handle:
            json.dump(out, file_handle)
    else:
        raise FileNotFoundError(args.file)