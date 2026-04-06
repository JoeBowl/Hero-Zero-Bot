# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 22:12:31 2026

@author: Chip7
"""

import json

def get_value(file_path, path, default=None):
    with open(file_path, 'r') as file:
        data = json.load(file)

    current = data
    for key in path:
        try:
            current = current[key]
        except (KeyError, TypeError):
            return default

    return current

def is_there_a_worldboss_event_going_on(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)
        
    worldboss_event_id = get_value(autoLoginUser_filepath, ["data", "character", "worldboss_event_id"])
    
    if worldboss_event_id == 0:
        return False
    
    worldboss_events = get_value(autoLoginUser_filepath, ["data", "worldboss_events"])
    if worldboss_events is None:
        return False
    
    for worldboss_event in worldboss_events:
        server_time = get_value(autoLoginUser_filepath, ["data", "server_time"])
        worldboss_event_ts_start = worldboss_event["ts_start"]
        worldboss_event_ts_end = worldboss_event["ts_end"]
        
        if server_time < worldboss_event_ts_start or server_time > worldboss_event_ts_end:
            return False
        
        player_level = get_value(autoLoginUser_filepath, ["data", "character", "level"])
        worldboss_event_min_level = worldboss_event["min_level"]
        worldboss_event_max_level = worldboss_event["max_level"]
        
        if player_level < worldboss_event_min_level or player_level > worldboss_event_max_level:
            return False
    
    return True
    
def start_world_boss_attack(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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
    DEFAULT_BODY["use_premium"] = "false"
    DEFAULT_BODY["action"] = "buyQuestEnergy"
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
        print("Quest energy purchased successfully")
    
        with open(autoLoginUser_file, 'r') as file:
            data = json.load(file)

        with open(autoLoginUser_file, 'w') as file:
            json.dump(merge_json(data, response_json), file, indent=4)
    else:
        print("Unable to purchase quest energy")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

if __name__ == "__main__":
    defaultHeaders_filepath = "src/defaultHeaders.txt"
    defaultBody_filepath = "src/defaultBody.txt"
    autoLoginUser_filepath = "src/autoLoginUser.json"
    log_filepath = "src/log.txt"
    COOLDOWN = 5
    
    server_time = get_value(autoLoginUser_filepath, ["data", "server_time"])
    print(server_time)
    print(is_there_a_worldboss_event_going_on(autoLoginUser_filepath))