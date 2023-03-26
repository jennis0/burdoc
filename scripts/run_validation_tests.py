import os
import sys
import json
import argparse
import shutil

from burdoc import BurdocParser

def run_parser(source_dir: str, out_dir: str, gold_dir: str, do_update: bool):

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    if not os.path.exists(gold_dir):
        os.makedirs(gold_dir)

    burdoc = BurdocParser()

    files = os.listdir(source_dir)
    for filename in files[-13:]:
        path = os.path.join(source_dir, filename)
        if not os.path.isfile(path):
            continue
        
        print(f"Reading {filename}")
        result = burdoc.read(path)

        json_filename = ".".join(filename.split(".")[:-1]) + ".json"
        out_path = os.path.join(out_dir, json_filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f)
        
        if do_update:
            gold_path = os.path.join(gold_dir, json_filename)
            shutil.copyfile(out_path, gold_path)

def run():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--source", type=str, help="Directory of input files", required=True)
    argparser.add_argument("--out", type=str, help="Target directory for output files", required=True)
    argparser.add_argument("--gold", type=str, required=False, help="Directory of gold files. These will be overwritten if --update is passed")
    argparser.add_argument("--update", required=False, default=False, action="store_true", help="Update gold files rather than run tests")
    args = argparser.parse_args()
    
    
    if not (os.path.exists(args.source) and os.path.isdir(args.source)):
        raise NotADirectoryError(f"{args.source} does not exist or is not a director")

    if not args.update and not (os.path.exists(args.gold) and os.path.isdir(args.gold)):
        raise NotADirectoryError(f"{args.gold}  does not exist or is not a director")

    if args.update and (os.path.exists(args.gold) and not os.path.isdir(args.gold)):
        raise NotADirectoryError(f"{args.gold}  does not exist or is not a director")
 
    if os.path.exists(args.out) and not os.path.isdir(args.out):
        raise NotADirectoryError(f"{args.out}  does not exist or is not a director")
    
    run_parser(args.source, args.out, args.gold, args.update)

if __name__ == "__main__":
    run()

