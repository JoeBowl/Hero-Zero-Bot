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

    # Export the response
    try:
        response_json = response.json()
        if not response_json['error']:
            with open(autoLoginUser_file, "w") as json_file:
                json.dump(response_json, json_file, indent=4)
                print(f"Response saved to {autoLoginUser_file}")
        else:
            raise RuntimeError(f"Response error|request_user_info: {response_json['error']}")
            
    except ValueError:
        with open(autoLoginUser_file + ".txt", "w") as txt_file:
            txt_file.write(response.text)

        raise RuntimeError("Response error|request_user_info: Response is not in JSON format.")

def get_current_energy(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["quest_energy"]

def get_active_quest_id(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["active_quest_id"]

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

def start_quest(best_quest, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "startQuest",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "quest_id": str(best_quest["id"])
        },
        success_msg=(
            f"Quest {best_quest['id']} launched successfully. "
            f"XP: {best_quest['rewards']}, "
            f"Energy: {best_quest['duration']/60}"
        ) if verbose else None,
        log_filepath=log_filepath
    )
    return response

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
    response = perform_request(
        "checkForQuestComplete",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "quest_id": "0"
        },
        ignore_errors=["errUserNotAuthorized"],
        success_msg="Quest completion verified" if verbose else None,
        log_filepath=log_filepath
    )
    return response

def claim_quest_rewards(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "claimQuestRewards",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "discard_item": "false",
            "refresh_inventory": "true"
        },
    #     headers_override={"TE": "trailers"},
        success_msg="Quest reward successfully collected" if verbose else None,
        log_filepath=log_filepath
    )
    return response

def buy_quest_energy(request_file, body_file, autoLoginUser_file, CONSTANTS, log_filepath=None, verbose=False):
    player_level = get_json_value(autoLoginUser_file, "data.character.level")
    energy_refilled_today = get_json_value(autoLoginUser_file, "data.character.quest_energy_refill_amount_today")
    game_currency = get_json_value(autoLoginUser_file, "data.character.game_currency")
    energy_refill_cost = get_energy_refill_cost(player_level, energy_refilled_today, CONSTANTS)
    print(
        f"Trying to buy energy!\n"
        f"Player level: {player_level} | Energy refilled today: {energy_refilled_today} | Game currency: {game_currency} | Refill cost: {energy_refill_cost}"
    )
    
    if energy_refilled_today >= CONSTANTS["quest_max_refill_amount_per_day"]:
        print("Energy refill limit reached!")
        return {"data": "", "error": "refillLimitReached"}
    
    if game_currency < get_energy_refill_cost(player_level, energy_refilled_today, CONSTANTS):
        raise RuntimeError("Not enough currency to refill energy!")
        
    response = buy_quest_energy_request(request_file, body_file, autoLoginUser_file, log_filepath, verbose)
    
    current_quest_energy = get_current_energy(autoLoginUser_file)
    print("quest_energy:", current_quest_energy)
    
    return response

def buy_quest_energy_request(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "buyQuestEnergy",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "use_premium": "false"
        },
        success_msg="Quest energy purchased successfully" if verbose else None,
        log_filepath=log_filepath
    )
    return response

def get_energy_refill_cost(level, energy_refilled_today, const):
    tier = energy_refilled_today // const["energy_per_refill"]
    tier = min(tier, len(const["cost_factors"]) - 1)

    c = const["coins_per_time"]
    base = round(c["base"] + c["scale"] * (c["level_scale"] * level) ** c["level_exp"], 3)
    
    return round(const["cost_factors"][tier] * base)

def claim_free_treasure_reveal_items(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "claimFreeTreasureRevealItems",
        request_file,
        body_file,
        autoLoginUser_file,
        success_msg="Free treasure reveal items claimed successfully" if verbose else None,
        log_filepath=log_filepath
    )
    return response

def collect_hideout_room(request_file, body_file, autoLoginUser_file, cooldown=0.75, log_filepath=None, collect=True, verbose=False):
    hideout_rooms = get_json_value(autoLoginUser_file, "data.hideout_rooms")
    
    rooms_to_collect = ["main_building", "stone_production", "glue_production"]
    ids_to_collect = []

    for hideout_room in hideout_rooms:
        identifier = hideout_room.get("identifier")

        if identifier in rooms_to_collect:
            id = hideout_room.get("id")
            ids_to_collect.append(id)

            current_resource_amount = hideout_room["current_resource_amount"]
            max_resource_amount = hideout_room["max_resource_amount"]
            
            if current_resource_amount >= 0.5*max_resource_amount:
                collect = True
                
    if collect:
        # Retry logic for collecting hideout rooms in case of errUserNotAuthorized
        retries = 0
        max_retries = 3
        while retries < max_retries:
            all_collected = True  # Flag to track if all rooms were successfully collected
            
            for hideout_room_id in ids_to_collect:
                response = collect_hideout_room_request(hideout_room_id, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)

                # Check if the error is "errUserNotAuthorized"
                if response.get("error") == "errUserNotAuthorized":
                    print("User not authorized. Requesting user info and retrying...")
                    request_user_info(request_file, body_file, autoLoginUser_file, verbose=verbose)
                    retries += 1
                    all_collected = False
                    time.sleep(cooldown)  # Give some time before retrying
                    break  # Exit the loop to retry collecting again

                time.sleep(cooldown)  # Sleep after successful collection

            # If no error was encountered, we can break out of the retry loop
            if all_collected:
                print("All hideout rooms collected successfully.")
                break

        else:
            raise RuntimeError("Max retries reached. Could not collect all hideout rooms.")
    else:
        print("No hideout rooms ready for collection.")

    return collect

def collect_hideout_room_request(hideout_room_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "collectHideoutRoomActivityResult", 
        request_file, 
        body_file, 
        autoLoginUser_file, 
        custom_body={
            "hideout_room_id": str(hideout_room_id),
            "collect": "true"
        },
        success_msg=f"Hideout room {hideout_room_id} successfully collected" if verbose else None,
        ignore_errors=["errUserNotAuthorized"], 
        log_filepath=log_filepath,
    )
    return response

def get_user_vouchers_request(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    with open(request_file, 'r') as f:
        raw_request = f.read()
    parsed_request = parse_request_with_body(raw_request, body_file)

    response = perform_request(
        "getStreamMessages",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "stream_type": "v",
            "stream_id": parsed_request["body"]["existing_user_id"],
            "start_message_id": "0"
        },
        success_msg="User vouchers retrieved successfully" if verbose else None,
        log_filepath=log_filepath
    )
    return response

def redeem_voucher_request(voucher_code, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "redeemVoucher",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "code": str(voucher_code)
        },
        success_msg="Voucher redeemed successfully" if verbose else None,
        log_filepath=log_filepath
    )
    return response
    
def get_energy_voucher(autoLoginUser_file):
    user_vouchers = get_json_value(autoLoginUser_file, "data.user_vouchers")
    
    for voucher in user_vouchers:
        rewards_raw = voucher.get("rewards", "{}")
        
        try:
            rewards = json.loads(rewards_raw)
        except (json.JSONDecodeError, TypeError):
            continue  # skip invalid entries
        
        # Check if there's exactly one reward and it's "quest_energy"
        if len(rewards) == 1 and "quest_energy" in rewards:
            return voucher
    
    return None

def redeem_energy_voucher(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    if verbose:
        print("Trying to redeem voucher")
    
    # Step 1: Try to get vouchers from local file
    user_vouchers = get_json_value(autoLoginUser_file, "data.user_vouchers")
    if user_vouchers is None:
        user_vouchers = []

    # Step 2: If no vouchers locally, fetch from server
    if not user_vouchers:
        if verbose:
            print("No vouchers found locally, fetching from server...")
        get_user_vouchers_request(request_file, body_file, autoLoginUser_file, log_filepath, verbose)
        user_vouchers = get_json_value(autoLoginUser_file, "data.user_vouchers")
        
    if user_vouchers is None:
        raise RuntimeError("redeem_energy_voucher: Unable to retrieve user vouchers from local file or server")
        
    if verbose:
        print(f"Found {len(user_vouchers)} vouchers")

    # Step 3: Find quest_energy voucher
    energy_voucher = None
    for voucher in user_vouchers:
        rewards_raw = voucher.get("rewards", "{}")
        try:
            rewards = json.loads(rewards_raw)
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(rewards, dict) and len(rewards) == 1 and "quest_energy" in rewards:
            energy_voucher = voucher
            break

    if not energy_voucher:
        if verbose:
            print("No quest_energy voucher found")
        return {"error": "noQuestEnergyVoucher"}

    # Step 4: Redeem the voucher
    voucher_code = energy_voucher.get("code")
    if not voucher_code:
        raise RuntimeError(f"redeem_energy_voucher: Unable to get voucher code for {energy_voucher}")

    if verbose:
        print(f"Redeeming quest_energy voucher: {voucher_code}")

    redeem_response = redeem_voucher_request(voucher_code, request_file, body_file, autoLoginUser_file, log_filepath, verbose)

    return redeem_response

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

def log_response(action, response, log_file='src/log.txt'):
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
        
def generate_auth(action, user_id):
    # The salt string
    salt = "GN1al351"
    
    # Combine action, salt, and user_id
    combined_string = action + salt + str(user_id)
    
    # Generate the MD5 hash of the combined string
    auth = hashlib.md5(combined_string.encode('utf-8')).hexdigest()
    
    return auth

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
        
def perform_request(action, request_file, body_file, autoLoginUser_file, custom_body=None, headers_override=None, success_msg=None, ignore_errors=None, log_filepath=None):
    with open(request_file, 'r') as f:
        raw_request = f.read()

    parsed_request = parse_request_with_body(raw_request, body_file)

    # Build the URL
    host = parsed_request["headers"]["Host"]
    path = parsed_request["path"]
    url = f"https://{host}{path}"

    # Get the headers
    headers = parsed_request["headers"].copy()
    if headers_override:
        headers.update(headers_override)

    # Base body
    body = {
        "action": action,
        "user_id": parsed_request["body"]["existing_user_id"],
        "user_session_id": parsed_request["body"]["existing_session_id"],
        "client_version": parsed_request["body"]["client_version"],
        "build_number": parsed_request["body"]["build_number"],
        "auth": generate_auth(action, parsed_request["body"]["existing_user_id"]),
        "rct": "2",
        "keep_active": parsed_request["body"]["keep_active"],
        "device_id": parsed_request["body"]["device_id"],
        "device_type": parsed_request["body"]["device_type"],
    }

    # Merge custom fields
    if custom_body:
        body.update(custom_body)

    encoded_body = urllib.parse.urlencode(body)
    
    # Commented because I've read that requests handles this automatically, so no need to set it up manually
    # headers["Content-Length"] = str(len(encoded_body))
    headers.pop("Content-Length", None)
    headers.pop("Accept-Encoding", None)
    headers.pop("Connection", None)
    
    # Send the POST request
    response = requests.post(url, headers=headers, data=encoded_body)

    if log_filepath:
        log_response(action, response, log_filepath)

    try:
        response_json = response.json()
    except ValueError:
        raise RuntimeError(f"{action} returned non-JSON response: {response.text[:200]}")

    ignore_errors = set(ignore_errors or [])
    if response_json["error"] == "":
        if success_msg:
            print(success_msg)

        with open(autoLoginUser_file, 'r') as f:
            data = json.load(f)

        with open(autoLoginUser_file, 'w') as f:
            json.dump(merge_json(data, response_json), f, indent=4)
    elif response_json["error"] in ignore_errors:
        pass
    else:
        raise RuntimeError(f"{action} failed: {response_json['error']}")

    return response_json