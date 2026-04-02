import urllib
import requests
from src.auth import generate_auth
import json
from src.bot2 import parse_request_with_body, log_response

def get_current_training_energy(autoLoginUser_path):
    with open(autoLoginUser_path, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["training_energy"]

def get_traing_time_left(autoLoginUser_path):
    with open(autoLoginUser_path, 'r') as file:
        data = json.load(file)
        
    server_time = data["data"]["server_time"]
    training_end_time = data["data"]["training"]["ts_end"]
    
    return training_end_time - server_time

def start_training(training_id, request_file, body_file, log_filepath=None, verbise=False):
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
        print(f"")
    else:
        print(f"")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

if __name__ == "__main__":
    defaultHeaders_filepath = "src/defaultHeaders.txt"
    defaultBody_filepath = "src/defaultBody.txt"
    autoLoginUser_filepath = "src/autoLoginUser.json"
    log_filepath = "src/log.txt"
    
    print(get_current_training_energy(autoLoginUser_filepath))
    print(get_traing_time_left(autoLoginUser_filepath))