import urllib
import requests
from src.auth import generate_auth
import json
from src.bot2 import parse_request_with_body, log_response

def collect_hideout_room(hideout_room_id, request_file, body_file, log_filepath=None, verbise=False):
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
    DEFAULT_BODY["hideout_room_id"] = str(hideout_room_id)
    DEFAULT_BODY["collect"] = "true"
    DEFAULT_BODY["action"] = "collectHideoutRoomActivityResult"
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
        print(f"Hideout room {hideout_room_id} successfully collected")
    else:
        print(f"Unable to collect hideout room {hideout_room_id}")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

if __name__ == "__main__":
    defaultHeaders_filepath = "src/defaultHeaders.txt"
    defaultBody_filepath = "src/defaultBody.txt"
    autoLoginUser_filepath = "src/autoLoginUser.json"
    log_filepath = "src/log.txt"
    
    collect_hideout_room(, defaultHeaders_filepath, defaultBody_filepath, log_filepath=log_filepath)