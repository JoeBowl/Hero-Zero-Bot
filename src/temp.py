import time
import json

def get_paths(d, prefix=""):
    paths = set()

    if isinstance(d, dict):
        for k, v in d.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            paths.add(new_prefix)
            paths.update(get_paths(v, new_prefix))

    elif isinstance(d, list):
        for i, item in enumerate(d):
            new_prefix = f"{prefix}[{i}]"
            paths.add(new_prefix)
            paths.update(get_paths(item, new_prefix))

    return paths

def merge_json(json1, json2):
    # If both are dicts → merge recursively
    if isinstance(json1, dict) and isinstance(json2, dict):
        for key, value in json2.items():
            if key in json1:
                json1[key] = merge_json(json1[key], value)
            else:
                json1[key] = value
        return json1

    # If both are lists → overwrite by index (like your compare logic)
    elif isinstance(json1, list) and isinstance(json2, list):
        for i, item in enumerate(json2):
            if i < len(json1):
                json1[i] = merge_json(json1[i], item)
            else:
                json1.append(item)
        return json1

    # Otherwise → overwrite value
    else:
        return json2

def compare_keys(json1, json2):
    paths1 = get_paths(json1)
    paths2 = get_paths(json2)

    missing = paths2 - paths1
    return missing

def sort_key(x):
    """Create a comparable key for any JSON-like object"""
    if isinstance(x, dict):
        return tuple(sorted((k, sort_key(v)) for k, v in x.items()))

    elif isinstance(x, list):
        return tuple(sorted(sort_key(i) for i in x))

    else:
        return x
    
def compare_values(json1, json2, path=""):
    diffs = []

    if isinstance(json2, dict):
        for key in json2:
            new_path = f"{path}.{key}" if path else key

            if key in json1:
                diffs.extend(compare_values(json1[key], json2[key], new_path))
            else:
                # Shouldn't happen if you already validated keys
                diffs.append((new_path, None, json2[key]))

    elif isinstance(json2, list):
        sorted1 = sorted(json1, key=sort_key)
        sorted2 = sorted(json2, key=sort_key)

        for i, item in enumerate(sorted2):
            new_path = f"{path}[{i}]"

            if i < len(sorted1):
                diffs.extend(compare_values(sorted1[i], item, new_path))
            else:
                diffs.append((new_path, None, item))

        # detect removed items
        for i in range(len(sorted2), len(sorted1)):
            diffs.append((f"{path}[{i}]", sorted1[i], None))

    else:
        # Compare actual values
        if json1 != json2:
            diffs.append((path, json1, json2))

    return diffs

# Function to read and load JSON data from files
def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

# Load JSON files
first_json = load_json("src/merged.json")
second_json = load_json("src/autoLoginUser2.json")

# Compare keys
missing_keys = compare_keys(first_json, second_json)

if not missing_keys:
    print("All keys from second JSON exist in first JSON ✅")
else:
    print("Missing keys:")
    for k in sorted(missing_keys):
        print(k)

# Compare values
differences = compare_values(first_json, second_json)

if not differences:
    print("No value differences 🎯")
else:
    print("Differences found:")
    for path, v1, v2 in differences:
        print(f"{path}: {v1} → {v2}")

# merged = merge_json(first_json, second_json)

# with open("src/merged.json", "w") as f:
#     json.dump(merged, f, indent=2)