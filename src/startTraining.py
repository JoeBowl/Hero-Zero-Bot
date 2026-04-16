from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import urllib
import requests
import json
from src.bot import generate_auth, parse_request_with_body, log_response, merge_json

def get_training_count(autoLoginUser_path):
    with open(autoLoginUser_path, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["training_count"]

def def_is_training_available(autoLoginUser_path):
    if get_training_pool(autoLoginUser_path) == "":
        return False
    else:
        return True

def get_training_pool(autoLoginUser_path):
    with open(autoLoginUser_path, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["training_pool"]

def get_current_training_energy(autoLoginUser_path):
    with open(autoLoginUser_path, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["training_energy"]

def get_active_training_id(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["active_quest_id"]

def get_traing_time_left(autoLoginUser_path):
    with open(autoLoginUser_path, 'r') as file:
        data = json.load(file)
        
    server_time = data["data"]["server_time"]
    training_end_time = data["data"]["training"]["ts_end"]
    
    return training_end_time - server_time

def start_training(training_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    with open(request_file, 'r') as f:
        raw_request = f.read()

    parsed_request = parse_request_with_body(raw_request, body_file)

    # Build the URL
    host = parsed_request["headers"]["Host"]
    path = parsed_request["path"]
    URL = f"https://{host}{path}"

    # Get the headers
    DEFAULT_HEADERS = parsed_request["headers"]

    # Get the body
    DEFAULT_BODY = {}
    DEFAULT_BODY["training_id"] = str(training_id)
    DEFAULT_BODY["refresh_trainings"] = "true"
    DEFAULT_BODY["action"] = "startTraining"
    DEFAULT_BODY["user_id"] = parsed_request["body"]["existing_user_id"]
    DEFAULT_BODY["user_session_id"] = parsed_request["body"]["existing_session_id"]
    DEFAULT_BODY["client_version"] = parsed_request["body"]["client_version"]
    DEFAULT_BODY["build_number"] = parsed_request["body"]["build_number"]
    DEFAULT_BODY["auth"] = generate_auth(DEFAULT_BODY["action"], DEFAULT_BODY["user_id"])
    DEFAULT_BODY["rct"] = "2"
    DEFAULT_BODY["keep_active"] = parsed_request["body"]["keep_active"]
    DEFAULT_BODY["device_id"] = parsed_request["body"]["device_id"]
    DEFAULT_BODY["device_type"] = parsed_request["body"]["device_type"]

    # Convert the body to x-www-form-urlencoded format
    body = urllib.parse.urlencode(DEFAULT_BODY)

    DEFAULT_HEADERS["Content-Length"] = str(len(body))

    # Send the POST request
    response = requests.post(URL, headers=DEFAULT_HEADERS, data=body)

    response_json = response.json()
    if response_json["error"] == "":
        print("Training started successfully")
    
        with open(autoLoginUser_file, 'r') as file:
            data = json.load(file)
    
        with open(autoLoginUser_file, 'w') as file:
            json.dump(merge_json(data, response_json), file, indent=4)
    else:
        print("Unable to start training")
    
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def get_best_training(autoLoginUser_file, weights, check_energy=True, verbose=False):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)
    
    inventory = data["data"]["inventory"]
    items = data["data"]["items"]

    best_quest = {
        "id": None,
        "duration": 0,
        "rewards": "{\"coins\":0,\"xp\":0}",
        "score": 0
    }

    if verbose:
        print(f"{'ID':<8} {'Dur(s)':<8} {'Coins':<8} {'XP':<8} "
              f"{'Score':<15} {'Rewards':<15}")
        print("-" * 85)

    # Loop through each quest in the JSON data
    for quest in data["data"]["quests"]:

if __name__ == "__main__":
    defaultHeaders_filepath = f"{BASE_DIR}/src/defaultHeaders.txt"
    defaultBody_filepath = f"{BASE_DIR}/src/defaultBody.txt"
    autoLoginUser_filepath = f"{BASE_DIR}/src/autoLoginUser2.json"
    log_filepath = f"{BASE_DIR}/src/log.txt"
    
    active_training = get_active_training_id(autoLoginUser_filepath)
    print("active_training:", active_training)
    
    if active_trainning == 0:
        print(get_training_count(autoLoginUser_filepath))
        
        print(def_is_training_available(autoLoginUser_filepath))
        print(get_training_pool(autoLoginUser_filepath))
    else:
        print(get_current_training_energy(autoLoginUser_filepath))
        print(get_traing_time_left(autoLoginUser_filepath))