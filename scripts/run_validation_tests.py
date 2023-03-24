import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.burdoc import BurdocParser

def run_validation(in_dir, out_dir):
    burdoc = BurdocParser()

    if not os.path.exists(in_dir) and os.path.isdir(in_dir):
        print(f"ERROR: {in_dir} does not exist or is not a director")
        exit(1)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    else:
        if not os.path.isdir(out_dir):
            print(f"ERROR: {out_dir} is not a directory")
            exit(1)

    files = os.listdir(in_dir)
    for filename in files[-13:]:
        path = os.path.join(in_dir, filename)
        if not os.path.isfile(path):
            continue
        
        print(f"Reading {filename}")
        result = burdoc.read(path, pages=[i for i in range(10)])

        json_filename = ".".join(filename.split(".")[:-1]) + ".json"
        json_path = os.path.join(out_dir, json_filename)
        with open(json_path, 'w') as f:
            json.dump(result, f)

if __name__ == "__main__":
    if len(sys.argv) != 4 and len(sys.argv) != 3:
        print("ERROR: Incorrect number of arguments. Use 'python run_validation_tests [in_dir] [out_dir] (gold)'")
        exit(1)
    
    run_validation(sys.argv[1], sys.argv[2])

