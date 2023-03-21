import os
from typing import Any
import json
import sys
import hashlib

def hash(obj):
    s = json.dumps(obj, sort_keys=True, indent=2)
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def diff_value(path, v1, v2):
    if v1 != v2:
        return [{'path':path, 'type':'change', 'old':v1, 'new':v2}]
    return []

def diff_dict(path, d1, d2):
    changes = []
    for k in d1:
        k_path = f"{path}.{k}"
        if k not in d2:
            changes.append({'path':k_path, 'type':'deletion', 'old':d1[k]})
        else:
            changes += do_diff(k_path, d1[k], d2[k])
    for k in d2:
        if k not in d1:
            changes.append({'path':k_path, 'type':'addition', 'new':d2[k]})
    return changes


def diff_list(path, l1, l2):
    changes = []
    l1_hashes = {hash(v):i for i,v in enumerate(l1)}
    l2_hashes = {hash(v):j for j,v in enumerate(l2)}

    for h in l1_hashes:
        l1_index = l1_hashes[h]
        if h not in l2_hashes:
            changes.append({'path':path, 'type':'deletion', 'old':l1[l1_index]})
            continue
        l2_index = l2_hashes[h]
        if l1_index != l2_index:
            changes.append({'path':path, 'type':'reorder', 'value':l1[l1_index], 'old':l1_index, 'new':l2_index})
        
        changes += do_diff(f"{path}.[{l1_index},{l2_index}]", l1[l1_index], l2[l2_index])

    for h in l2_hashes:
        if h not in l1_hashes:
            changes.append({'path':path, 'type':'addition', 'new':l2[l2_hashes[h]]})

    return changes              


def do_diff(path, v1, v2):
    v1_type = type(v1).__name__
    v2_type = type(v2).__name__
    if v1_type != v2_type:
        return [{'path':path, 'type':'change', 'old':v1, 'new':v2}]
    
    if isinstance(v1, dict):
        return diff_dict(path, v1, v2)
    
    if isinstance(v1, list):
        return diff_list(path, v1, v2)
    
    return diff_value(path, v1, v2)

def compare_files(f1: os.PathLike, f2: os.PathLike) -> Any:
    with open(f1, 'r') as f:
        d1 = json.load(f)
        with open(f2, 'r') as f:
            d2 = json.load(f)
            
            diff = diff_dict("root", d1['json'], d2['json'])

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