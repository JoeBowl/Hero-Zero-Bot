import urllib
import requests
import datetime
import hashlib
import json
import time
from functools import reduce
import operator

def request_user_info(request_file, body_file, autoLoginUser_file, verbose=False):
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
        response_json = response.json()  # Parse JSON response
        
        if not response_json['error']:
            # Save the JSON response
            with open(autoLoginUser_file, "w") as json_file:
                json.dump(response_json, json_file, indent=4)
                print(f"Response saved to {autoLoginUser_file}")
        else:
            raise RuntimeError(f"Response error|request_user_info: {response_json['error']}")
    except ValueError:
        # Save raw text with .txt suffix
        with open(autoLoginUser_file + ".txt", "w") as txt_file:
            txt_file.write(response.text)

        raise RuntimeError(f"Response error|request_user_info: Response is not in JSON format.")

def generate_auth(action, user_id):
    # The salt string
    salt = "GN1al351"
    
    # Combine action, salt, and user_id
    combined_string = action + salt + str(user_id)
    
    # Generate the MD5 hash of the combined string
    auth = hashlib.md5(combined_string.encode('utf-8')).hexdigest()
    
    return auth

def get_server_time(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["server_time"]

def get_current_energy(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["quest_energy"]

def get_active_quest_id(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["active_quest_id"]

def get_quest_energy_refilled_today(autoLoginUser_file): 
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["quest_energy_refill_amount_today"]

def get_game_currency(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["game_currency"]

def get_player_level(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["level"]

def get_best_quest(autoLoginUser_file, weights, check_energy=True, verbose=False):
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
                raise RuntimeError(
                    f"{quest_id:<8} {duration:<8.0f} {rewards.get('coins', 0):<8} "
                    f"{rewards.get('xp', 0):<8} {score:<15.2f} {rewards}\n"
                    f"Reward weight not defined for key={key}, value={value}"
                )

        # Weighted score
        score = score / duration

        # Add quest type multiplier
        if quest["fight_npc_identifier"] == "":
            score = score * weights[("timer", None)]
        else:
            score = score * weights[("fight", None)]

        if verbose:
            print(f"{quest_id:<8} {duration:<8.0f} {rewards.get("coins", 0):<8} {rewards.get("xp", 0):<8} "
                  f"{score:<15.2f} {rewards}")
        
        # Skip if not enough energy
        if check_energy:
            current_quest_energy = get_current_energy(autoLoginUser_file)
            if quest["energy_cost"] > current_quest_energy:
                continue

        if score > best_quest["score"]:
            best_quest = quest.copy()
            best_quest["score"] = score

    if verbose:
        print(f"Best quest: {best_quest['id']} | Duration: {best_quest['duration']/60:.1f} min | Rewards: {best_quest['rewards']}")

    return best_quest

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

def start_quest(best_quest, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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
    DEFAULT_BODY["quest_id"] = str(best_quest['id'])
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
        print(f"Quest {best_quest['id']} launched successfully. "
              f"XP: {best_quest['rewards']}, "
              f"Energy: {best_quest['duration']/60}")
        
        with open(autoLoginUser_file, 'r') as file:
            data = json.load(file)

        with open(autoLoginUser_file, 'w') as file:
            json.dump(merge_json(data, response_json), file, indent=4)
    else:
        print(f"Unable to start quest {best_quest["id"]}")
        print(response_json)
    
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def check_for_quest_complete(request_file, body_file, autoLoginUser_file, cooldown=60, log_filepath=None, verbose=False):
    start_time = time.time()
    while time.time() - start_time < 5*cooldown:
        response = check_for_quest_complete_request(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath)
        
        if not response['error']:  # handles None or ""
            break
        elif response['error'] == "errFinishNotYetCompleted":
            print(f"Quest not finished yet. Waiting {cooldown} seconds before retrying...")
            time.sleep(cooldown)
        elif response['error'] == "errUserNotAuthorized":
            print(f"User not authorized. Refreshing user info and retrying in {cooldown} seconds...")
            request_user_info(request_file, body_file, autoLoginUser_file, verbose=False)
            time.sleep(cooldown)
        else:
            raise RuntimeError(f"Unexpected error: {response['error']}")
    
    return response

def check_for_quest_complete_request(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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

        with open(autoLoginUser_file, 'r') as file:
            data = json.load(file)

        with open(autoLoginUser_file, 'w') as file:
            json.dump(merge_json(data, response_json), file, indent=4)
    else:
        print("Unable to verify quest completion")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def claim_quest_rewards(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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

        with open(autoLoginUser_file, 'r') as file:
            data = json.load(file)

        with open(autoLoginUser_file, 'w') as file:
            json.dump(merge_json(data, response_json), file, indent=4)
    else:
        print("Unable to collect quest reward")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def buy_quest_energy(request_file, body_file, autoLoginUser_file, CONSTANTS, log_filepath=None, verbose=False):
    player_level = get_player_level(autoLoginUser_file)
    energy_refilled_today = get_quest_energy_refilled_today(autoLoginUser_file)
    game_currency = get_game_currency(autoLoginUser_file)
    energy_refill_cost = get_energy_refill_cost(player_level, energy_refilled_today, CONSTANTS)
    print(
        f"Trying to buy energy!\n"
        f"Player level: {player_level} | Energy refilled today: {energy_refilled_today} | Game currency: {game_currency} | Refill cost: {energy_refill_cost}"
    )
    
    if energy_refilled_today >= CONSTANTS["quest_max_refill_amount_per_day"]:
        raise RuntimeError("Energy refill limit reached!")
    
    if game_currency < get_energy_refill_cost(player_level, energy_refilled_today, CONSTANTS):
        raise RuntimeError("Not enough currency to refill energy!")
        
    response = buy_quest_energy_request(request_file, body_file, autoLoginUser_file, log_filepath, verbose)
    
    current_quest_energy = get_current_energy(autoLoginUser_file)
    print("quest_energy:", current_quest_energy)
    
    return response

def buy_quest_energy_request(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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

def game_currency_per_time(level, const):
    c = const["coins_per_time"]
    return round(c["base"] + c["scale"] * (c["level_scale"] * level) ** c["level_exp"], 3)

def get_energy_refill_cost(level, energy_refilled_today, const):
    tier = energy_refilled_today // const["energy_per_refill"]
    tier = min(tier, len(const["cost_factors"]) - 1)

    base = game_currency_per_time(level, const)
    return round(const["cost_factors"][tier] * base)

def claim_free_treasure_reveal_items(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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
    DEFAULT_BODY["action"] = "claimFreeTreasureRevealItems"
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
        print("Free treasure reveal items claimed successfully")

        with open(autoLoginUser_file, 'r') as file:
            data = json.load(file)

        with open(autoLoginUser_file, 'w') as file:
            json.dump(merge_json(data, response_json), file, indent=4)
    else:
        print("Unable to claim free treasure reveal items")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def collect_hideout_room(request_file, body_file, autoLoginUser_file, cooldown=0.75, log_filepath=None, verbose=False):
    hideout_rooms = get_json_value(autoLoginUser_file, "data.hideout_rooms")
    
    rooms_to_collect = ["main_building", "stone_production", "glue_production"]
    ids_to_collect = []

    collect = False
    for hideout_room in hideout_rooms:
        identifier = hideout_room.get("identifier")

        if identifier in rooms_to_collect:
            id = hideout_room.get("id")
            ids_to_collect.append(id)

            current_resource_amount = hideout_room["current_resource_amount"]
            max_resource_amount = hideout_room["max_resource_amount"]
            
            if current_resource_amount >= 0.5*max_resource_amount:
                collect = True

    if collect == True:
        for hideout_room_id in ids_to_collect:
            response = collect_hideout_room_request(hideout_room_id, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            time.sleep(cooldown)
    else:
        print("No hideout rooms ready for collection.")

    return collect

def collect_hideout_room_request(hideout_room_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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
        
        with open(autoLoginUser_file, 'r') as file:
            data = json.load(file)

        with open(autoLoginUser_file, 'w') as file:
            json.dump(merge_json(data, response_json), file, indent=4)
    else:
        print(f"Unable to collect hideout room {hideout_room_id}")
        
    if log_filepath:
        log_response(DEFAULT_BODY["action"], response, log_filepath)

    return response_json

def get_json_value(filepath, path, default=None):
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Convert dot-separated string to list of keys
    if isinstance(path, str):
        path = path.split(".")
    
    try:
        return reduce(operator.getitem, path, data)
    except (KeyError, IndexError, TypeError):
        return default


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

def merge_json(json1, json2, path=None):
    if path is None:
        path = []

    # If both are dicts → merge recursively
    if isinstance(json1, dict) and isinstance(json2, dict):
        for key, value in json2.items():
            if key in json1:
                json1[key] = merge_json(json1[key], value, path + [key])
            else:
                json1[key] = value
        return json1

    # Special case: path == ["data", "items"] → append lists (no duplicates by id)
    elif path == ["data", "items"] and isinstance(json1, list) and isinstance(json2, list):
        existing_ids = {item["id"] for item in json1}
        return json1 + [item for item in json2 if item["id"] not in existing_ids]

    # If both are lists → overwrite
    elif isinstance(json2, list):
        return json2

    # Otherwise → overwrite value
    else:
        return json2