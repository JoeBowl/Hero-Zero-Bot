import urllib
import requests
import json
from bot import generate_auth, parse_request_with_body

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

def find_inventory_upgrades(autoLoginUser_filepath, verbose=False):
    with open(autoLoginUser_filepath, 'r') as file:
        data = json.load(file)
    
    inventory = data["data"]["inventory"]
    items = data["data"]["items"]
    
    items_by_id = {item["id"]: item for item in items}

    bag_item_ids = [
        v for k, v in inventory.items()
        if k.startswith("bag_item") and v != 0
    ]

    best_per_type = {}

    if verbose:
        print(f"{'ItemID':<8} {'Type':<6} {'EquippedID':<12} "
              f"{'OldScore':<10} {'NewScore':<10} {'Upgrade':<10}")
        print("-" * 70)

    for item_id in bag_item_ids:
        item = items_by_id.get(item_id)
        if not item:
            continue
        
        item_type = item["type"]
        equipped_item = get_equipped_item(inventory, items, item_type)

        new_score = get_item_score(item)
        old_score = get_item_score(equipped_item) if equipped_item else 0
        upgrade_value = new_score - old_score

        if verbose:
            print(f"{item_id:<8} {item_type:<6} "
                  f"{(equipped_item['id'] if equipped_item else 'None'):<12} "
                  f"{old_score:<10.2f} {new_score:<10.2f} {upgrade_value:<10.2f}")

        if upgrade_value <= 0:
            continue

        # Keep best per type directly
        current_best = best_per_type.get(item_type)
        if not current_best or upgrade_value > current_best["upgrade"]:
            best_per_type[item_type] = {
                "item_id": item_id,
                "type": item_type,
                "equipped_id": equipped_item["id"] if equipped_item else None,
                "old_score": old_score,
                "new_score": new_score,
                "upgrade": upgrade_value
            }
    
    # Keep only the best upgrade per item type
    best_per_type = {}

    # Final sorted list
    return sorted(best_per_type.values(), key=lambda x: x["upgrade"], reverse=True)

def equip_best_item(item, request_file, body_file, verbose=False):
    with open(request_file, 'r') as f:
        raw_request = f.read()

    parsed_request = parse_request_with_body(raw_request, body_file)

    item_id = item["item_id"]
    target_slot = item["type"]

    # Build the URL
    host = parsed_request["headers"]["Host"]
    path = parsed_request["path"]
    URL = f"https://{host}{path}"

    # Get the headers
    DEFAULT_HEADERS = parsed_request["headers"].copy()
    DEFAULT_HEADERS["Priority"] = "u=0"

    # Get the body
    DEFAULT_BODY = {}
    DEFAULT_BODY["item_id"] = str(item_id)
    DEFAULT_BODY["target_slot"] = str(target_slot)
    DEFAULT_BODY["action_type"] = "3"
    DEFAULT_BODY["action"] = "moveInventoryItem"
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

    if verbose:
        print("URL:", URL)
        print("BODY:", DEFAULT_BODY)
        print("STATUS:", response.status_code)
        print("RESPONSE:", response.text[:200])

    return response

if __name__ == "__main__":
    defaultHeaders_filepath = "src/defaultHeaders.txt"
    defaultBody_filepath = "src/defaultBody.txt"
    autoLoginUser_filepath = "src/autoLoginUser.json"

    upgrades = find_inventory_upgrades(autoLoginUser_filepath, verbose=True)

    print("Upgrades:")
    for upgrade in upgrades:
        # equip_best_item(upgrade, defaultHeaders_filepath, defaultBody_filepath)
        print(upgrade)