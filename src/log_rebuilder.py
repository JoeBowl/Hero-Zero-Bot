from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import src.bot as bot
import json
import copy

def dict_diff(d1, d2, path=""):
    diffs = []

    for key in d1.keys() | d2.keys():
        new_path = f"{path}.{key}" if path else key

        if key not in d1:
            diffs.append(f"Added: {new_path} = {d2[key]}")
        elif key not in d2:
            diffs.append(f"Removed: {new_path}")
        else:
            if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                diffs.extend(dict_diff(d1[key], d2[key], new_path))
            elif d1[key] != d2[key]:
                diffs.append(f"Changed: {new_path}: {d1[key]} → {d2[key]}")

    return diffs

log_filepath = f"{BASE_DIR}/src/log.txt"

before = {}
after = {}

with open(log_filepath, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, start=1):

        if i >= 3127:
            before = after
            update = json.loads(line)
            after = bot.merge_json(copy.deepcopy(before), copy.deepcopy(update["response_json"]))
            print(f"{i} | action: {update["action"]}")

        if i >= 3153:
            break

with open("src/temp.json", "w") as file:
    json.dump(before, file, indent=4)

with open("src/temp2.json", "w") as file:
    json.dump(update, file, indent=4)

with open("src/temp3.json", "w") as file:
    json.dump(after, file, indent=4)

# diffs = dict_diff(before, after)
# for di in diffs:
#     print(di)

a = {"data": {"training": {}}}
b = bot.merge_json(copy.deepcopy(after), copy.deepcopy(a))

with open("src/temp4.json", "w") as file:
    json.dump(b, file, indent=4)
