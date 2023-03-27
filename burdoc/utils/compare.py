from typing import Any, Dict, List
import json
import hashlib

def _hash(obj):
    s = json.dumps(obj, sort_keys=True, indent=2)
    return hashlib.md5(s.encode('utf-8'), usedforsecurity=False).hexdigest()

def _diff_value(path: str, value1: Any, value2: Any) -> List[Dict[str, Any]]:
    if value1 != value2:
        return [{'path':path, 'type':'change', 'old':value1, 'new':value2}]
    return []

def _diff_dict(path: str, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes = []
    for k in dict1:
        if path != "":
            k_path = f"{path}.{k}"
        else:
            k_path = k
        if k not in dict2:
            changes.append({'path':k_path, 'type':'deletion', 'old':dict1[k]})
        else:
            changes += _do_diff(k_path, dict1[k], dict2[k])
    for k in dict2:
        if k not in dict1:
            changes.append({'path':k_path, 'type':'addition', 'new':dict2[k]})
    return changes


def _diff_list(path: str, list1: List[Any], list2: List[Any]) -> List[Dict[str, Any]]:
    changes = []
    l1_hashes = {_hash(v):i for i,v in enumerate(list1)}
    l2_hashes = {_hash(v):j for j,v in enumerate(list2)}

    for h in l1_hashes:
        l1_index = l1_hashes[h]
        if h not in l2_hashes:
            changes.append({'path':path, 'type':'deletion', 'old':list1[l1_index]})
            continue
        l2_index = l2_hashes[h]
        if l1_index != l2_index:
            changes.append({'path':path, 'type':'reorder', 'value':list1[l1_index], 'old':l1_index, 'new':l2_index})
        
        changes += _do_diff(f"{path}.[{l1_index},{l2_index}]", list1[l1_index], list2[l2_index])

    for h in l2_hashes:
        if h not in l1_hashes:
            changes.append({'path':path, 'type':'addition', 'new':list2[l2_hashes[h]]})

    return changes              


def _do_diff(path: str, obj1: Any, obj2: Any) -> List[Dict[str, Any]]:
    v1_type = type(obj1).__name__
    v2_type = type(obj2).__name__
    if v1_type != v2_type:
        return [{'path':path, 'type':'change', 'old':obj1, 'new':obj2}]
    
    if isinstance(obj1, dict):
        return _diff_dict(path, obj1, obj2)
    
    if isinstance(obj1, list):
        return _diff_list(path, obj1, obj2)
    
    return _diff_value(path, obj1, obj2)

def compare(obj1: Dict[str, Any], obj2: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compares to JSON objects generated by burdoc and returns a list of changes.
    Unlike most dictionary comparison systems, this detects re-orderings as well as changes

    Args:
        obj1 (Dict[str, Any]): A JSON output from Burdoc
        obj2 (Dict[str, Any]): A JSON output from Burdoc

    Returns:
        List[Dict[str, Any]]: A list of changes in format:
            [
                {'path':path to change in object, 'type':[change, addition, deletion, reorder], 'old':old value, 'new':new value, 'value':value of the object (only used for reorder)}
            ]
    """
    changes = _do_diff("", obj1, obj2)
    return changes