import argparse
import json
import os
import re
import shutil
import time
from typing import Any, Dict, List, Optional

from burdoc import BurdocParser
from burdoc.utils.compare import compare


def build_file_list(directory: str, file_type:str, exclude: List[str], include: List[str], root: Optional[str]=None) -> Dict[str, str]:
    """Builds a dictionary of valid files with key being a directory-aware title and the value being the relative path.

    Args:
        directory (str): Root directory to start the search
        file_type (str): File type to accept (e.g. '.pdf', or '.json')
        exclude (List[str]): List of regexes that will be compared against the file stem and any files matching at least one will be excluded
        include (List[str]): List of regexes that will be compared against the file stem and only files matching at least one will be included.
        root (Optional[str], optional): Additional directory path to attach to the start of each stem

    Returns:
        Dict[str, str]: 
        {
            root_file: /path/to/directory/root_file.file_type,
            dir1/file: /path/to/directory/dir1/file.file_type,
            dir2/file: /path/to/directory/dir2/file.file_type,
        }
    """
    files = os.listdir(directory)
    filtered_files: Dict[str, str] = {}
    
    for f in files:
        path = os.path.join(directory, f)
        
        if os.path.isdir(os.path.join(directory, f)):
            if root:
                this_root = os.path.join(root, f)
            else:
                this_root = f
            filtered_files |= build_file_list(os.path.join(directory, f), file_type, exclude, include, root=this_root)
        
        if not os.path.isfile(path):
            continue
        
        if not f.endswith(file_type):
            continue
            
        stem = os.path.join(root, f[:-len(file_type)]) if root else f[:-len(file_type)]
            
        if len(exclude) > 0:
            if any(re.match(e, stem) for e in exclude):
                continue
        
        if len(include) > 0:
            if any(re.match(i, stem) for i in include):
                filtered_files[stem] = path
            continue
            
        filtered_files[stem] = path
        
    return filtered_files

def run_parser(source_dir: str, out_dir: str, gold_dir: str, do_update: bool, 
               exclude: List[str], include: List[str]) -> Dict[str, Any]:
           
    if not (os.path.exists(source_dir) and os.path.isdir(source_dir)):
        raise NotADirectoryError(f"{source_dir} does not exist or is not a directory")

    if do_update:
        if (os.path.exists(gold_dir) and not os.path.isdir(gold_dir)):
            raise NotADirectoryError(f"{gold_dir}  does not exist or is not a directory")
        elif not os.path.exists(gold_dir):
            os.makedirs(gold_dir)
    elif not (os.path.exists(gold_dir) and os.path.isdir(gold_dir)):
        raise NotADirectoryError(f"{gold_dir}  does not exist or is not a directory")
 
    if out_dir and os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise NotADirectoryError(f"{out_dir}  does not exist or is not a directory")
    elif out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
        
    test_data = {'in_dir':source_dir, 'out_dir':out_dir, 'gold_dir':gold_dir, 'files': []}
                
    in_files = build_file_list(source_dir, ".pdf", exclude, include)
    gold_files = build_file_list(gold_dir, ".json", exclude, include)
    
    print(in_files)
    
    if not do_update and in_files.keys() != gold_files.keys():
        extra_in = [f for f in in_files if f not in gold_files]
        extra_gold = [f for f in gold_files if f not in in_files]
        message_parts = ["Inconsistent file set for validation testing."]
        if len(extra_gold) > 0:
            message_parts.append(f"Missing input files for testing={extra_gold}")
        if len(extra_in) > 0:
            message_parts.append(f"Missing gold files for testing={extra_in}")
        raise RuntimeError("\n".join(message_parts))

    burdoc = BurdocParser()

    for filetitle, filename in in_files.items():
        
        if not os.path.isfile(filename):
            continue
        
        test_data['files'].append({'filename':filename, 'filetitle':filetitle, 'changes':{}})
        
        print(f"Reading {filename}")
        start = time.perf_counter()
        json_out = burdoc.read(filename)
        test_data['files'][-1]['processing_time'] = round(time.perf_counter() - start, 3)

        json_filename = filetitle + ".json"
        gold_path = os.path.join(gold_dir, json_filename) 
        
        #Round-trip via JSON for consistency
        json_out = json.loads(json.dumps(json_out))
        
        if not do_update or filename in gold_files:
                            
            with open(gold_path, 'r', encoding='utf-8') as f_gold: 
                print("Running comparison")
                json_gold = json.load(f_gold)
                test_data['files'][-1]['changes']  = compare(json_gold, json_out)
                print(f"Found {len(test_data['files'][-1]['changes'])} changes")
            
        if out_dir:
            
            out_path = os.path.join(out_dir, json_filename)
            if not os.path.exists(os.path.dirname(out_path)):
                os.makedirs(os.path.dirname(out_path))
            
            with open(out_path, 'w', encoding='utf-8') as f_out:
                print(f"Writing result to {out_path}")
                json.dump(json_out, f_out)
            
        if do_update:
            
            if not os.path.exists(os.path.dirname(gold_path)):
                os.makedirs(os.path.dirname(gold_path))
            
            with open(gold_path, 'w', encoding='utf-8') as f_gold:
                print(f"Updating gold result in {gold_path}")
                json.dump(json_out, f_gold)
                
    return test_data

def print_results(report_data: Dict[str, Any]):
    print("========================================================================")
    print("                            Validation Report                           ")
    print("------------------------------------------------------------------------")
    print(f"Source File Directory = {report_data['in_dir']}")
    print(f"Output File Directory = {report_data['out_dir']}")
    print(f"Gold File Directory   = {report_data['gold_dir']}")
    print("------------------------------------------------------------------------")
    for result in report_data['files']:
        adds = [c for c in result['changes'] if c['type'] == 'addition']
        dels = [c for c in result['changes'] if c['type'] == 'deletion']
        reorders = [c for c in result['changes'] if c['type'] == 'reorder']
        changes = [c for c in result['changes'] if c['type'] == 'change']
        print(f"File={result['filename']}")
        print(f"Processing Time={result['processing_time']} \t#Changes={len(result['changes'])}")
        print(f"Added={len(adds)}  \tRemoved={len(dels)}\tReordered={len(reorders)}\tChanged={len(changes)}")
        print("------------------------------------------------------------------------")
    print("========================================================================")

def run():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--source", "-s", type=str, help="Directory of input files", required=True)
    argparser.add_argument("--out", "-o", type=str, help="Target directory for output files", required=False)
    argparser.add_argument("--gold", "-g", type=str, required=True, help="Directory of gold files. These will be overwritten if --update is passed")
    argparser.add_argument("--report", "-r", type=str, help="Location to write detailed report")
    argparser.add_argument("--update", required=False, default=False, action="store_true", help="Update gold files rather than run tests")
    argparser.add_argument("--exclude", type=str, required=False, default=[])
    argparser.add_argument("--include", type=str, required=False, default=[])
    args = argparser.parse_args()
    
    if len(args.include) > 0 and len(args.exclude) > 0:
        raise RuntimeError("Cannot specify both include and exclude lists")
    
    report_data = run_parser(args.source, args.out, args.gold, args.update, 
                             args.exclude.split(",") if args.exclude else [],
                             args.include.split(",") if args.include else []
                             )
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f_report:
            json.dump(report_data, f_report)
    else:
        print_results(report_data)
            

if __name__ == "__main__":
    run()

