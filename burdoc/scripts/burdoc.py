import argparse
import json
import logging
import os

from ..burdoc_parser import BurdocParser


def run():
    """Run the BurdocParser in the command line
    """
    argparser = argparse.ArgumentParser()

    argparser.add_argument("file", type=str, help="Path to the PDF file you want to prase")
    argparser.add_argument('outfile', type=str, help="Path to file to write output to", nargs="?")
    argparser.add_argument('--mltables', action='store_true', required=False, default=False, help="Use ML table finding. Warning, this can be slow without GPU acceleration")
    argparser.add_argument('--images', action='store_true', required=False, default=False, help="Extract images from PDF and store in output. This can lead to very large output JSON files.")

    args = argparser.parse_args()

    parser = BurdocParser(log_level=logging.INFO, 
                          use_ml_table_finding=args.mltables)

    if os.path.exists(args.file):
        print(f"Parsing {args.file}")
        out = parser.read(args.file)

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