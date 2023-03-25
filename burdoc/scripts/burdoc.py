import argparse
import json
import logging
import os

from ..burdoc_parser import BurdocParser


def run():
    argparser = argparse.ArgumentParser()

    argparser.add_argument("file", type=str, help="Path to the PDF file you want to prase")
    argparser.add_argument('outfile', type=str, help="Path to file to write output to", nargs="?")

    args = argparser.parse_args()

    parser = BurdocParser(log_level=logging.INFO)

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
        with open(outfile, 'w') as f:
            json.dump(out, f)
    else:
        raise FileNotFoundError(args.file)