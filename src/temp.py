import time
import json


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

def get_best_quest(autoLoginUser_filepath, verbose=False,
                   XP_WEIGHT = 1.0,
                   COIN_WEIGHT = 0.5,
                   UPGRADE_WEIGHT = 10e4):
    
    with open(autoLoginUser_filepath, 'r') as file:
        data = json.load(file)
    
    inventory = data["data"]["inventory"]
    items = data["data"]["items"]

    best_quest = {
        "id": None,
        "duration": 0,
        "rewards": "{\"coins\":0,\"xp\":0}",
        "item_upgrade": 0,
        "score": 0
    }

    if verbose:
        print(f"{'ID':<8} {'Dur(s)':<8} {'Coins':<8} {'XP':<8} "
              f"{'Upgrade':<10} {'Score':<15} {'Rewards':<15}")
        print("-" * 85)

    # Loop through each quest in the JSON data
    for quest in data["data"]["quests"]:
        quest_id = quest["id"]
        duration = quest["duration"]
        rewards = json.loads(quest["rewards"])

        coins = rewards["coins"]
        xp = rewards["xp"]
        item_id = rewards.get("item")

        if item_id:
            upgrade_value = get_upgrade_value(item_id, inventory, items)
        else:
            upgrade_value = 0

        # Avoid division by zero
        if duration == 0:
            duration = 1e-6

        # Weighted score
        score = (
            xp * XP_WEIGHT +
            coins * COIN_WEIGHT +
            upgrade_value * UPGRADE_WEIGHT
        ) / duration

        if verbose:
            print(f"{quest_id:<8} {duration:<8.0f} {coins:<8} {xp:<8} "
                  f"{upgrade_value:<10.0f} {score:<15.2f} {rewards}")
            
        for i in rewards:
            if i != "coins" and i != "xp" and rewards[i] != "server_launch_blooming_nature_lotus":
                time.sleep(10e4)

        if score > best_quest["score"]:
            best_quest = quest.copy()
            best_quest["score"] = score

    return best_quest

def get_best_quest2(autoLoginUser_filepath, weights, verbose=False):
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
                score += upgrade_value * weights.get(("item", None), 0)
                continue
            
            # Compute score for stackable rewards (xp, coins...)
            if isinstance(value, (int, float)) or str(value).isdigit():
                value = int(value)
                weight_key = (key, None)
                score += value * weights.get(weight_key, 0)

            # Compute score for non-stackable rewards
            elif isinstance(value, str):
                weight_key = (key, value)
                score += weights.get(weight_key, 0)

            # Unknown -> wait for further inspection
            else:
                print(f"{quest_id:<8} {duration:<8.0f} {rewards.get("coins", 0):<8} {rewards.get("xp", 0):<8} "
                      f"{score:<15.2f} {rewards}")
                time.sleep(10e4)

        # Weighted score
        score = score / duration

        if verbose:
            print(f"{quest_id:<8} {duration:<8.0f} {rewards.get("coins", 0):<8} {rewards.get("xp", 0):<8} "
                  f"{score:<15.2f} {rewards}")

        if score > best_quest["score"]:
            best_quest = quest.copy()
            best_quest["score"] = score

    return best_quest

REWARD_WEIGHTS = {
    # Standard resources
    ("xp", None): 1.0,
    ("coins", None): 1.0,

    # Upgrade system
    ("item", None): 1e5,

    # Event-specific rewards
    ("event_item", "server_launch_blooming_nature_lotus"): 0,
    ("slotmachine_jetons", None): 1e4,
}

autoLoginUser_filepath = "src/autoLoginUser.json"
get_best_quest2(autoLoginUser_filepath, REWARD_WEIGHTS, verbose=True)