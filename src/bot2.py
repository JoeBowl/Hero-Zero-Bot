import urllib
import requests
from src.auth import generate_auth
import datetime
import json
import time

def request_user_info(request_file, body_file, login_user_json_path, verbose=False):
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
    DEFAULT_BODY = parsed_request["body"]
    DEFAULT_BODY["auth"] = generate_auth(DEFAULT_BODY["action"], DEFAULT_BODY["user_id"])

    # Convert the body to x-www-form-urlencoded format
    body = urllib.parse.urlencode(DEFAULT_BODY)

    DEFAULT_HEADERS["Content-Length"] = str(len(body))

    # Send the POST request
    response = requests.post(URL, headers=DEFAULT_HEADERS, data=body)

    # Print the response to check
    if verbose:
        print(response)

    # Export the response
    try:
        data = response.json()  # Parse JSON response
        
        # Save the JSON response
        with open(login_user_json_path, "w") as json_file:
            json.dump(data, json_file, indent=4)
            print("Response saved to autoLoginUser.json")
    except ValueError:
        print("Response is not in JSON format.")
        
        # Save raw text with .txt suffix
        with open(login_user_json_path + ".txt", "w") as txt_file:
            txt_file.write(response.text)

def get_current_energy(autoLoginUser_path):
    with open(autoLoginUser_path, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["quest_energy"]

def get_item_score(item):
    return (
        item.get("stat_stamina", 0) +
        item.get("stat_strength", 0) +
        item.get("stat_critical_rating", 0) +
        item.get("stat_dodge_rating", 0)
    )

def get_equipped_item(inventory, items, item_type):
    slot_map = {
        1: "mask_item_id",
        2: "cape_item_id",
        3: "suit_item_id",
        4: "belt_item_id",
        5: "boots_item_id",
        6: "weapon_item_id",
        7: "gadget_item_id",
    }

    slot = slot_map.get(item_type)
    if not slot:
        return None

    equipped_id = inventory.get(slot, 0)
    if equipped_id == 0:
        return None

    return next((i for i in items if i["id"] == equipped_id), None)

def get_upgrade_value(item_id, inventory, items):
    reward_item = next((i for i in items if i["id"] == item_id), None)
    if not reward_item:
        return 0

    equipped_item = get_equipped_item(inventory, items, reward_item["type"])

    reward_score = get_item_score(reward_item)
    equipped_score = get_item_score(equipped_item) if equipped_item else 0
    return reward_score - equipped_score

def get_best_quest(autoLoginUser_filepath, weights, check_energy=True, verbose=False):
    with open(autoLoginUser_filepath, 'r') as file:
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
        quest_id = quest["id"]
        duration = quest["duration"]
        rewards = json.loads(quest["rewards"])

        if duration == 0:
            duration = 1e-6

        score = 0
        for key, value in rewards.items():            
            # Compute score for item upgrade
            if key == "item":
                upgrade_value = get_upgrade_value(value, inventory, items)
                score += max(0, upgrade_value) * weights.get(("item", None), 0)
                continue
            
            # Compute score for stackable rewards (xp, coins...)
            if isinstance(value, (int, float)) or str(value).isdigit():
                value = int(value)
                weight_key = (key, None)
                score += value * weights.get(weight_key, 0)

            # Compute score for non-stackable rewards
            elif isinstance(value, str):
                if (key, value) in weights:
                    score += weights[(key, value)]
                elif (key, None) in weights:
                    score += weights[(key, None)]

            # Unknown -> wait for further inspection
            if (key, value) not in weights and (key, None) not in weights:
                print(f"{quest_id:<8} {duration:<8.0f} {rewards.get("coins", 0):<8} {rewards.get("xp", 0):<8} "
                      f"{score:<15.2f} {rewards}")
                time.sleep(10e4)

        # Weighted score
        score = score / duration

        if verbose:
            print(f"{quest_id:<8} {duration:<8.0f} {rewards.get("coins", 0):<8} {rewards.get("xp", 0):<8} "
                  f"{score:<15.2f} {rewards}")
        
        # Skip if not enough energy
        if check_energy:
            current_quest_energy = get_current_energy(autoLoginUser_filepath)
            if quest["energy_cost"] > current_quest_energy:
                continue

        if score > best_quest["score"]:
            best_quest = quest.copy()
            best_quest["score"] = score

    return best_quest

def parse_request_with_body(request_txt, body_txt):
    # Parsing the request headers (same as before)
    lines = request_txt.strip().splitlines()
    method, path, protocol = lines[0].split(" ")

    headers = {}
    for line in lines[1:]:
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key] = value

    # Parsing the body (form data) from the body.txt file
    body = {}
    with open(body_txt, 'r') as f:
        body_data = f.read().strip().splitlines()

    for line in body_data:
        if '=' in line:
            key, value = line.split('=', 1)
            body[key] = urllib.parse.unquote(value)  # decode URL-encoded characters if needed

    # Combine everything into a final dictionary
    return {
        "method": method,
        "path": path,
        "protocol": protocol,
        "headers": headers,
        "body": body
    }

def start_quest(quest_id, request_file, body_file, log_filepath=None, verbose=False):
    with open(request_file, 'r') as f:
        raw_request = f.read()

    parsed_request = parse_request_with_body(raw_request, body_file)

    # Build the URL
    host = parsed_request["headers"]["Host"]
    path = parsed_request["path"]
    URL = f"https://{host}{path}"

    # Get the headers
    DEFAULT_HEADERS = parsed_request["headers"]
    DEFAULT_HEADERS["Priority"] = "u=0"

    # Get the body
    DEFAULT_BODY = {}
    DEFAULT_BODY["quest_id"] = str(quest_id)
    DEFAULT_BODY["action"] = "startQuest"
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
        print(f"Quest {best_quest["id"]} launched successfully. "
              f"XP: {best_quest['rewards']}, "
              f"Energy: {best_quest['duration']/60}")
    else:
        print(f"Unable to start quest {best_quest["id"]}")
        print(response_json)
    
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def check_for_quest_complete(request_file, body_file, log_filepath=None, verbose=False):
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
    DEFAULT_BODY["quest_id"] = "0"
    DEFAULT_BODY["action"] = "checkForQuestComplete"
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
        print("Quest completed successfully verified")
    else:
        print("Unable to verify quest completion")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def claim_quest_rewards(request_file, body_file, log_filepath=None, verbose=False):
    with open(request_file, 'r') as f:
        raw_request = f.read()

    parsed_request = parse_request_with_body(raw_request, body_file)

    # Build the URL
    host = parsed_request["headers"]["Host"]
    path = parsed_request["path"]
    URL = f"https://{host}{path}"

    # Get the headers
    DEFAULT_HEADERS = parsed_request["headers"]
    DEFAULT_HEADERS["TE"] = "trailers"

    # Get the body
    DEFAULT_BODY = {}
    DEFAULT_BODY["discard_item"] = "false"
    DEFAULT_BODY["refresh_inventory"] = "true"
    DEFAULT_BODY["action"] = "claimQuestRewards"
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
        print("Quest reward successfully collected")
    else:
        print("Unable to collect quest reward")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def log_response(action, response, log_file='quest_log.txt'):
    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Prepare the log entry
    log_entry = {
        'timestamp': timestamp,
        'action': action,
        'status_code': response.status_code,
        'response_json': response.json()
    }

    # Write the log entry to the file
    with open(log_file, 'a') as log:
        log.write(json.dumps(log_entry) + '\n')

if __name__ == "__main__":
    defaultHeaders_filepath = "src/defaultHeaders.txt"
    defaultBody_filepath = "src/defaultBody.txt"
    autoLoginUser_filepath = "src/autoLoginUser.json"
    log_filepath = "src/log.txt"
    COOLDOWN = 5

    REWARD_WEIGHTS = {
        # Standard resources
        ("xp", None): 1.0,
        ("coins", None): 1.0,
        ("premium", None): 1e10,

        # Upgrade system
        ("item", None): 2e3,

        # Event-specific rewards
        ("dungeon_key", None): 1e5,
        ('herobook_item_epic', None): 1e5,
        ("herobook_item_rare", None): 2e3,
        ("herobook_item_common", None): 2e3,
        ('story_dungeon_item', 'storydungeon1_4_laundry'): 2e3,
        ("event_item", "server_launch_blooming_nature_lotus"): 0,
        ("slotmachine_jetons", None): 1e3,
        ("event_item", 'easter_eggs'): 2e3,
        ("event_item", 'easter_bunnies'): 2e3,
    }

    for i in range(15):
        request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, verbose=False)

        current_quest_energy = get_current_energy(autoLoginUser_filepath)
        print("quest_energy:", current_quest_energy)

        best_quest = get_best_quest(autoLoginUser_filepath, REWARD_WEIGHTS, check_energy=False, verbose=True)
        best_quest_id = str(best_quest["id"])
        print("Best quest:", best_quest["id"], best_quest["duration"]/60, best_quest["rewards"])
        
        # Check if best_quest is valid
        if not best_quest or best_quest["id"] is None:
            print("No valid quest found. Breaking loop.")
            break
        elif best_quest["energy_cost"] > current_quest_energy:
            print(f"Not enough energy for quest {best_quest['id']}. Required: {best_quest['energy_cost']}, Available: {current_quest_energy}. Breaking loop.")
            break
        # break

        # Start a quest
        response = start_quest(best_quest_id, defaultHeaders_filepath, defaultBody_filepath, log_filepath=log_filepath)
        
        wait_time = best_quest['duration'] + COOLDOWN
        finish_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        print(f"Waiting {wait_time / 60:.0f} min (until {finish_time.strftime('%H:%M:%S')})")
        time.sleep(best_quest['duration'] + COOLDOWN)

        # Check if quest is finished
        # If quest isn't finished yet, try again. If quest isn't finished after 5 tries, break
        start_time = time.time()
        while time.time() - start_time < COOLDOWN*10:
            response = check_for_quest_complete(defaultHeaders_filepath, defaultBody_filepath, log_filepath=log_filepath)
            
            if not response['error']:  # handles None or ""
                break
            elif response['error'] == "errFinishNotYetCompleted":
                time.sleep(COOLDOWN*2)
            else: 
                print(f"Unexpected error: {response['error']}")
                break

        # Claim quest rewards
        response = claim_quest_rewards(defaultHeaders_filepath, defaultBody_filepath, log_filepath=log_filepath)