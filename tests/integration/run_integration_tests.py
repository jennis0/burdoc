import argparse
import json
import os
import re
import sys
import time
import datetime
from typing import Any, Dict, List, Optional

from burdoc import BurdocParser
from burdoc.utils.compare import compare


def get_data_dir() -> str:
    """Get the local directory storing test data

    Returns:
        str: Local data directory
    """
    return os.path.join(os.path.dirname(__file__), 'data')


def build_file_list(directory: str, file_type: str, exclude: List[str], include: List[str], root: Optional[str] = None) -> Dict[str, str]:
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
            filtered_files |= build_file_list(os.path.join(
                directory, f), file_type, exclude, include, root=this_root)

        if not os.path.isfile(path):
            continue

        if not f.endswith(file_type):
            continue

        stem = os.path.join(root, f[:-len(file_type)]
                            ) if root else f[:-len(file_type)]

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
    """Run the parser over all files and check for changes

    Args:
        source_dir (str): Input file directory
        out_dir (str): Directory to store any test outputs
        gold_dir (str): Gold file directory
        do_update (bool): Whether to update the gold files after running
        exclude (List[str]): List of regexes used to exclude files from testing
        include (List[str]): List of regexes used to inlucde files in testing

    Raises:
        NotADirectoryError: One of the source, out, gold directories are not directories
        RuntimeError: Something else went wrong

    Returns:
        Dict[str, Any]: {
            in_dir: input directory,
            out_dir: output directory,
            gold_dir: gold directory,
            files: {
                filename: short file name,
                filepath: full path,
                changes: list of changes between generated json and the gold
            }
        }
    """

    if not (os.path.exists(source_dir) and os.path.isdir(source_dir)):
        raise NotADirectoryError(
            f"{source_dir} does not exist or is not a directory")

    if do_update:
        if (os.path.exists(gold_dir) and not os.path.isdir(gold_dir)):
            raise NotADirectoryError(
                f"{gold_dir}  does not exist or is not a directory")
        elif not os.path.exists(gold_dir):
            os.makedirs(gold_dir)
    elif not (os.path.exists(gold_dir) and os.path.isdir(gold_dir)):
        raise NotADirectoryError(
            f"{gold_dir}  does not exist or is not a directory")

    if out_dir and os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise NotADirectoryError(
            f"{out_dir}  does not exist or is not a directory")
    elif out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)

    test_data = {'in_dir': source_dir, 'out_dir': out_dir,
                 'gold_dir': gold_dir, 'files': {}}

    in_files = build_file_list(source_dir, ".pdf", exclude, include)
    gold_files = build_file_list(gold_dir, ".json", exclude, include)

    if not do_update and in_files.keys() != gold_files.keys():
        extra_in = [f for f in in_files if f not in gold_files]
        extra_gold = [f for f in gold_files if f not in in_files]
        message_parts = ["Inconsistent file set for validation testing."]
        if len(extra_gold) > 0:
            message_parts.append(
                f"Missing input files for testing={extra_gold}")
        if len(extra_in) > 0:
            message_parts.append(f"Missing gold files for testing={extra_in}")
        raise RuntimeError("\n".join(message_parts))

    burdoc = BurdocParser(detailed=True)

    for filetitle, filename in in_files.items():

        if not os.path.isfile(filename):
            continue

        test_data['files'][filetitle] = {
            'filename': filename, 'filetitle': filetitle, 'changes': {}}

        print(f"Reading {filename}")
        start = time.perf_counter()
        json_out = burdoc.read(filename)
        test_data['files'][filetitle]['processing_time'] = round(
            time.perf_counter() - start, 3)

        json_filename = filetitle + ".json"
        gold_path = os.path.join(gold_dir, json_filename)

        # Round-trip via JSON for consistency
        json_out = json.loads(json.dumps(json_out))

        if not do_update or filename in gold_files:

            with open(gold_path, 'r', encoding='utf-8') as f_gold:
                print("Running comparison")
                json_gold = json.load(f_gold)
                test_data['files'][filetitle]['changes'] = compare(
                    json_gold, json_out, ignore_paths=['metadata.path'])
                print(
                    f"Found {len(test_data['files'][filetitle]['changes'])} changes")
                test_data['files'][filetitle]['time'] = datetime.datetime.now().strftime("%m/%d/%Y-%H:%M:%S")

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
    print("==========================================================================================================")
    print("                                              Validation Report                                           ")
    print("----------------------------------------------------------------------------------------------------------")
    print(f"Source File Directory = {report_data['in_dir']}")
    print(f"Output File Directory = {report_data['out_dir']}")
    print(f"Gold File Directory   = {report_data['gold_dir']}")
    print("----------------------------------------------------------------------------------------------------------")
    for filetitle, result in report_data['files'].items():
        adds = [c for c in result['changes'] if c['type'] == 'addition']
        dels = [c for c in result['changes'] if c['type'] == 'deletion']
        reorders = [c for c in result['changes'] if c['type'] == 'reorder']
        changes = [c for c in result['changes'] if c['type'] == 'change']
        print(f"File={filetitle}")
        print(
            f"Processing Time={result['processing_time']} \t#Changes={len(result['changes'])}")
        print(
            f"Added={len(adds)}  \tRemoved={len(dels)}\tReordered={len(reorders)}\tChanged={len(changes)}")
        print("----------------------------------------------------------------------------------------------------------")
    
    print(f"Total Time: {report_data['processing_time']}")
    print("==========================================================================================================")


def run():
    """Parse local arguments and run tests

    Raises:
        RuntimeError: _description_
    """
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--test-dir", "-s", type=str,
                           help="Directory of files. Defaults to standard location", required=False, default=None)
    argparser.add_argument("--update", required=False, default=False,
                           action="store_true", help="Update gold files rather than run tests")
    argparser.add_argument("--exclude", type=str, required=False, default=[])
    argparser.add_argument("--include", type=str, required=False, default=[])
    args = argparser.parse_args()

    data_dir = get_data_dir()
    if not args.test_dir:
        args.test_dir = data_dir

    inputs = os.path.join(args.test_dir, "inputs")
    outputs = os.path.join(args.test_dir, 'outputs')
    gold = os.path.join(args.test_dir, 'gold')
    report = os.path.join(args.test_dir, 'report.json')

    if len(args.include) > 0 and len(args.exclude) > 0:
        raise RuntimeError("Cannot specify both include and exclude lists")

    start = time.perf_counter()
    report_data = run_parser(inputs, outputs, gold, args.update,
                             args.exclude.split(",") if args.exclude else [],
                             args.include.split(",") if args.include else []
                             )
    report_data['processing_time'] = round(time.perf_counter() - start, 3)
    report_data['timestamp'] = datetime.datetime.now().strftime("%m/%d/%Y-%H:%M:%S")

    print_results(report_data)

    if args.include or args.exclude and os.path.exists(report):
        with open(report, 'r', encoding='utf-8') as f_report:
            old_report = json.load(f_report)
            for file in report_data['files']:
                old_report['files'][file] = report_data['files'][file]
            
            report_data = old_report
    
    with open(report, 'w', encoding='utf-8') as f_report:
        json.dump(report_data, f_report)


    for _, report_item in report_data['files'].items():
        if len(report_item['changes']) > 0:
            print("Tests Failed. Found changes to validation data.")
            sys.exit(1)


if __name__ == "__main__":
    run()
