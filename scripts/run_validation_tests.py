import argparse
import json
import os
import shutil
import time
from typing import Any, Dict, List

from burdoc import BurdocParser
from burdoc.utils.compare import compare


def build_file_list(directory: str, file_type:str, exclude: List[str]) -> Dict[str, str]:
    files = os.listdir(directory)
    files = {f[:-len(file_type)]: f for f in files if f.endswith(file_type) and f[:-len(file_type)] not in exclude}
    return files

def run_parser(source_dir: str, out_dir: str, gold_dir: str, do_update: bool, exclude: List[str]) -> Dict[str, Any]:
           
    if not (os.path.exists(source_dir) and os.path.isdir(source_dir)):
        raise NotADirectoryError(f"{source_dir} does not exist or is not a directory")

    if do_update:
        if (os.path.exists(gold_dir) and not os.path.isdir(gold_dir)):
            raise NotADirectoryError(f"{gold_dir}  does not exist or is not a directory")
        elif not os.path.exists(gold_dir):
            os.makedirs(gold_dir)
    elif not (os.path.exists(gold_dir) and os.path.isdir(gold_dir)):
        raise NotADirectoryError(f"{gold_dir}  does not exist or is not a directory")
 
    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise NotADirectoryError(f"{out_dir}  does not exist or is not a directory")
    elif not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
        
    test_data = {'in_dir':source_dir, 'out_dir':out_dir, 'gold_dir':gold_dir, 'files': []}
        
    print(exclude)
        
    in_files = build_file_list(source_dir, ".pdf", exclude)
    gold_files = build_file_list(gold_dir, ".json", exclude)
    
    if not do_update and in_files != gold_files:
        extra_in = [f for f in in_files if f not in gold_files]
        extra_gold = [f for f in gold_files if f not in in_files]
        message_parts = ["Inconsistent file set for validation testing."]
        if len(extra_gold) > 0:
            message_parts.append(f"Missing input files for testing={extra_gold}")
        if len(extra_in) > 0:
            message_parts.append(f"Missing gold files for testing={extra_in}")
        raise RuntimeError("\n".join(message_parts))

    burdoc = BurdocParser()
    changes = {}

    for filetitle, filename in in_files.items():
        
        path = os.path.join(source_dir, filename)
        if not os.path.isfile(path):
            continue
        
        test_data['files'].append({'filename':filename, 'filetitle':filetitle})
        
        print(f"Reading {filename}")
        start = time.perf_counter()
        json_out = burdoc.read(path)
        test_data['files'][-1]['processing_time'] = round(time.perf_counter() - start, 3)

        json_filename = filetitle + ".json"
        out_path = os.path.join(out_dir, json_filename)
        with open(out_path, 'w', encoding='utf-8') as f_out:
            print(f"Writing result to {out_path}")
            json.dump(json_out, f_out)
        
        gold_path = os.path.join(gold_dir, json_filename)
        if do_update:
            print(f"Writing gold result to {gold_path}")
            shutil.copyfile(out_path, gold_path)
            continue
        
        with open(gold_path, 'r', encoding='utf-8') as f_gold: 
            print("Running comparison")
            json_gold = json.load(f_gold)
            changes[filename] = compare(json_gold, json_out)
            print(f"Found {len(changes[filename])} changes")
            
    return changes

def run():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--source", type=str, help="Directory of input files", required=True)
    argparser.add_argument("--out", type=str, help="Target directory for output files", required=True)
    argparser.add_argument("--gold", type=str, required=False, help="Directory of gold files. These will be overwritten if --update is passed")
    argparser.add_argument("--update", required=False, default=False, action="store_true", help="Update gold files rather than run tests")
    argparser.add_argument("--exclude", type=str, required=False, default=[])
    args = argparser.parse_args()
    

    
    run_parser(args.source, args.out, args.gold, args.update, args.exclude.split(","))

if __name__ == "__main__":
    run()

