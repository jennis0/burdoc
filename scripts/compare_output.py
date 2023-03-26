import os
from typing import Any
import json
import sys

from burdoc.utils.compare import compare


def compare_files(file1: str, file2: str) -> Any:
    with open(file1, 'r') as f:
        d1 = json.load(f)
        with open(file2, 'r') as f:
            d2 = json.load(f)
            
            diff = compare(d1['json'], d2['json'])

    return diff

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("ERROR: Requires two files as argument and a diff path")

    f1s = os.listdir(sys.argv[1])
    f2s = os.listdir(sys.argv[2])
    diff_path = sys.argv[3]

    if not os.path.exists(sys.argv[3]):
        os.makedirs(sys.argv[3])

    for f in f1s:
        if f not in f2s:
            continue
    
        f1 = os.path.join(sys.argv[1], f)
        f2 = os.path.join(sys.argv[2], f)
        if not os.path.isfile(f1) or not os.path.isfile(f2):
            continue

        diff = compare_files(f1, f2)
            
        out_f = os.path.join(sys.argv[3],"diff_"+f)
        with open(out_f, 'w') as f_handle:
            json.dump(diff, f_handle)