import urllib
import requests
import datetime
import hashlib
import json
import time
import numpy as np
from functools import reduce
import operator

def get_current_energy(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["quest_energy"]

def get_active_quest_id(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["active_quest_id"]

def get_stats(character):
    return (
        character["stat_total_stamina"] +
        character["stat_total_strength"] +
        character["stat_total_critical_rating"] +
        character["stat_total_dodge_rating"]
    )

def get_energy_refill_cost(level, energy_refilled_today, contants_data):
    cost_factors = [
        contants_data["quest_energy_refill1_cost_factor"],
        contants_data["quest_energy_refill2_cost_factor"],
        contants_data["quest_energy_refill3_cost_factor"],
        contants_data["quest_energy_refill4_cost_factor"],
        contants_data["quest_energy_refill5_cost_factor"],
        contants_data["quest_energy_refill6_cost_factor"],
        contants_data["quest_energy_refill7_cost_factor"],
        contants_data["quest_energy_refill8_cost_factor"]
    ]
    c = {
        "base": contants_data["coins_per_time_base"],
        "scale": contants_data["coins_per_time_scale"],
        "level_scale": contants_data["coins_per_time_level_scale"],
        "level_exp": contants_data["coins_per_time_level_exp"]
    }
    tier = energy_refilled_today // contants_data["quest_energy_refill_amount"]
    tier = min(tier, len(cost_factors) - 1)

    base = round(c["base"] + c["scale"] * (c["level_scale"] * level) ** c["level_exp"], 3)
    
    return round(cost_factors[tier] * base)
    
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

def get_league_rewards(autoLoginUser_file, verbose=False):
    with open(autoLoginUser_file, 'r') as f:
        data = json.load(f)
    
    my_id = data["data"]["character"]["id"]
    
    if my_id == data["data"]["league_fight"]["character_a_id"]:
        me = "a"
    elif my_id == data["data"]["league_fight"]["character_b_id"]:
        me = "b"
    else:
        raise RuntimeError("get_duel_rewards: Im none?")
    
    winner = data["data"]["battle"]["winner"]
    rewards = json.loads(data["data"]["league_fight"][f"character_{me}_rewards"])
    opponent_name = data["data"]["opponent"]["name"]
    
    if verbose:
        if winner == me:
            print(f"League fight won against {opponent_name}. Rewards: {rewards}")
        else:
            print(f"League fight against {opponent_name}. Rewards: {rewards}")
    
    return winner == me, rewards

def get_duel_rewards(autoLoginUser_file, verbose=False):
    with open(autoLoginUser_file, 'r') as f:
        data = json.load(f)
    
    my_id = data["data"]["character"]["id"]
    
    if my_id == data["data"]["duel"]["character_a_id"]:
        me = "a"
    elif my_id == data["data"]["duel"]["character_b_id"]:
        me = "b"
    else:
        raise RuntimeError("get_duel_rewards: Im none?")
    
    winner = data["data"]["battle"]["winner"]
    rewards = json.loads(data["data"]["duel"][f"character_{me}_rewards"])
    opponent_name = data["data"]["opponent"]["name"]
    
    if verbose:
        if winner == me:
            print(f"Duel won against {opponent_name}. Rewards: {rewards}")
        else:
            print(f"Duel lost against {opponent_name}. Rewards: {rewards}")
    
    return winner == me, rewards
    
def get_league_opponents_in_my_guild(autoLoginUser_file):
    if get_json_value(autoLoginUser_file, "data.character.guild_id") == 0:
        return []
    
    with open(autoLoginUser_file, 'r') as f:
        data = json.load(f)

    opponents_names = {
        opponent["opponent"]["name"] for opponent in data["data"]["league_opponents"]
    }

    guild_members_names = {
        member["name"] for member in data["data"]["guild_members"]
    }

    return list(opponents_names & guild_members_names)

def get_duel_opponents_in_my_guild(autoLoginUser_file):
    if get_json_value(autoLoginUser_file, "data.character.guild_id") == 0:
        return []
    
    with open(autoLoginUser_file, 'r') as f:
        data = json.load(f)

    opponents_names = {
        opponent["name"] for opponent in data["data"]["opponents"]
    }

    guild_members_names = {
        member["name"] for member in data["data"]["guild_members"]
    }

    return list(opponents_names & guild_members_names)

def get_best_quest(autoLoginUser_file, constants_file, weights, quest_type = "data.quests", max_energy=1e10, verbose=False):
    inventory = get_json_value(autoLoginUser_file, "data.inventory")
    items = get_json_value(autoLoginUser_file, "data.items")
    
    with open(constants_file, "r", encoding="utf-8") as f:
        contants_data = json.load(f)
    
    best_quest = {
        "id": None,
        "energy_cost": 999,
        "rewards": "{\"coins\":0,\"xp\":0}",
        "score": 0
    }

    if verbose:
        print(f"{'ID':<8} {'Cost':<8} {'Score':<15} {'Rewards':<15}")
        print("-" * 85)

    # Loop through each quest in the JSON data
    for quest in get_json_value(autoLoginUser_file, quest_type):
        quest_id = quest["id"]
        quest_cost = quest["energy_cost"]
        rewards = json.loads(quest["rewards"])

        if quest_cost == 0:
            quest_cost = 1e-6

        score = 0
        for key, value in rewards.items():            
            # Compute score for item upgrade and new item
            if key == "item":
                upgrade_value = get_upgrade_value(value, autoLoginUser_file, contants_data, verbose=False)
                score += max(0, upgrade_value) * weights.get(("item", None), 0)
                
                if is_new_item(value, items, autoLoginUser_file):
                    score += weights[("new_item", None)]
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
                    f"{quest_id:<8} {quest_cost:<8.0f} {score:<15.2f} {rewards}\n"
                    f"Reward weight not defined for key={key}, value={value}"
                )

        # Weighted score
        score = score / (quest_cost*60)

        # Add quest type multiplier
        if quest["fight_difficulty"] == 0:
            score = score * weights[("timer", None)]
        else:
            score = score * weights[("fight", None)]

        if verbose:
            print(f"{quest_id:<8} {quest_cost:<8.0f} {score:<15.2f} {rewards}")
        
        if quest["energy_cost"] > max_energy:
            continue
        
        if score > best_quest["score"]:
            best_quest = quest.copy()
            best_quest["score"] = score

    if verbose:
        print(f"Best quest: {best_quest['id']} | Cost: {best_quest['energy_cost']} energy | Rewards: {best_quest['rewards']}")

    return best_quest

def is_new_item(value, items, autoLoginUser_file):
    owned_items = get_json_value(autoLoginUser_file, "data.owned_items")
    
    identifier = next(
        (item["identifier"] for item in items if item["id"] == value),
        None
    )
    
    if identifier is None:
        raise ValueError(f"is_new_item: Item with id {value} not found in items")
    
    found = any(
        owned_item["identifier"] == identifier
        for owned_item in owned_items
    )
    
    return not found

def score_state(autoLoginUser_file, contants_data, override_item=None):
    # VALID_SLOTS definition
    VALID_SLOTS = {
        "mask_item_id",
        "cape_item_id",
        "suit_item_id",
        "belt_item_id",
        "boots_item_id",
        "weapon_item_id",
        "gadget_item_id",
    }
    
    inventory = get_json_value(autoLoginUser_file, "data.inventory")
    items = get_json_value(autoLoginUser_file, "data.items")
    
    # Fetch character stats directly
    character_data = get_json_value(autoLoginUser_file, "data.character")
    characters_stats = [
        character_data["stat_base_stamina"],
        character_data["stat_base_strength"],
        character_data["stat_base_critical_rating"],
        character_data["stat_base_dodge_rating"],
    ]

    equipped = []
    set_counts = {}

    # Build equipped items and set counts
    for slot, item_id in inventory.items():
        if slot not in VALID_SLOTS:
            continue

        if not item_id or item_id <= 0:
            continue

        item = next((i for i in items if i["id"] == item_id), None)
        if item:
            equipped.append(item)

    # Simulate the swap with the override item if needed
    if override_item:
        equipped = [
            override_item if i["type"] == override_item["type"] else i
            for i in equipped
        ]
        if override_item["type"] not in [i["type"] for i in equipped]:
            equipped.append(override_item)

    # Build set counts inside the state
    for item in equipped:
        template = contants_data["item_templates"][item['identifier']]
        set_id = template.get("item_set_identifier")

        if set_id:
            set_counts[set_id] = set_counts.get(set_id, 0) + 1

    total = 0

    # Add base stats for each equipped item
    for item in equipped:
        total += (
            item.get("stat_stamina", 0) +
            item.get("stat_strength", 0) +
            item.get("stat_critical_rating", 0) +
            item.get("stat_dodge_rating", 0)
        )

    # Add set bonuses once per set
    for set_id, count in set_counts.items():
        bonuses = contants_data["item_set_templates"][set_id]["bonus"]

        for threshold, bonus in bonuses.items():
            if count >= int(threshold):
                total += int(np.floor(bonus["value"] * characters_stats[bonus["type"] - 1]))

    return total

def get_upgrade_value(item_id, autoLoginUser_file, contants_data, verbose=False):
    items = get_json_value(autoLoginUser_file, "data.items")
    
    reward_item = next((i for i in items if i["id"] == item_id), None)
    
    if not reward_item:
        if verbose:
            print(f"Item with ID {item_id} not found!")
        return 0

    # current build
    current_score = score_state(autoLoginUser_file, contants_data)

    # simulated build with reward item
    new_score = score_state(autoLoginUser_file, contants_data, reward_item)
    
    # Calculate the score difference
    score_difference = new_score - current_score
    
    # if verbose:
    #     print("Item ID:", item_id)
    #     print(f"Current Score: {current_score}")
    #     print(f"New Score: {new_score}")
    #     print(f"Score Difference: {score_difference}")

    return score_difference

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
        ),
        log_filepath=log_filepath,
        verbose=verbose
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
        success_msg="Quest completion verified",
        log_filepath=log_filepath,
        verbose=verbose
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
        # headers_override={"TE": "trailers"},
        success_msg="Quest reward successfully collected",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def buy_quest_energy(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=None, verbose=False):
    player_level = get_json_value(autoLoginUser_file, "data.character.level")
    energy_refilled_today = get_json_value(autoLoginUser_file, "data.character.quest_energy_refill_amount_today")
    game_currency = get_json_value(autoLoginUser_file, "data.character.game_currency")
    
    with open(constants_file, "r", encoding="utf-8") as f:
        contants_data = json.load(f)
        
    energy_refill_cost = get_energy_refill_cost(player_level, energy_refilled_today, contants_data)
    print(
        f"Trying to buy energy!\n"
        f"Player level: {player_level} | Energy refilled today: {energy_refilled_today} | Game currency: {game_currency} | Refill cost: {energy_refill_cost}"
    )
    
    if energy_refilled_today >= contants_data["quest_max_refill_amount_per_day"]:
        print("Energy refill limit reached!")
        return {"data": "", "error": "refillLimitReached"}
    
    if game_currency < energy_refill_cost:
        print("Not enough currency to refill energy!")
        return {"data": "", "error": "refillLimitReached"}
        
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
        success_msg="Quest energy purchased successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def claim_free_treasure_reveal_items(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "claimFreeTreasureRevealItems",
        request_file,
        body_file,
        autoLoginUser_file,
        success_msg="Free treasure reveal items claimed successfully",
        ignore_errors=["errClaimFreeTreasureRevealItemsCooldownActive"], 
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def collect_hideout_room(request_file, body_file, autoLoginUser_file, cooldown=0.75, log_filepath=None, verbose=False):
    def is_collectible(room, collected_ids, target_ids):
        return (
            room.get("id") not in collected_ids
            and room.get("identifier") in target_ids
            and room.get("status") == 6
        )
    hideout_rooms = get_json_value(autoLoginUser_file, "data.hideout_rooms")
    rooms_to_collect = {"main_building", "stone_production", "glue_production", "xp_production"}
    collected_room_ids = set()
                
    # Retry logic for collecting hideout rooms in case of failure
    retries = 0
    max_retries = 2
    while retries < max_retries:
        hideout_rooms = get_json_value(autoLoginUser_file, "data.hideout_rooms")

        for hideout_room in hideout_rooms:
            room_id = hideout_room.get("id")

            if not is_collectible(hideout_room, collected_room_ids, rooms_to_collect):
                continue

            response = collect_hideout_room_request(room_id, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)

            error = response.get("error")
            if error == "errCollectActivityResultInvalidStatus":
                print(f"Error '{error}' for room {room_id}. Refreshing state...")
                request_user_info(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
                break  # re-scan fresh snapshot next iteration
            else:
                collected_room_ids.add(room_id)

            time.sleep(cooldown)  # Sleep after successful collection
        
        remainings = any(is_collectible(room, collected_room_ids, rooms_to_collect) for room in hideout_rooms)
        if not remainings:
            break

        retries += 1
    
    if remainings:
        raise RuntimeError("Max retries reached. Could not collect all hideout rooms.")
    
    if verbose:
        print("All hideout rooms collected successfully.")

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
        success_msg=f"Hideout room {hideout_room_id} successfully collected",
        ignore_errors=["errCollectActivityResultInvalidStatus"], 
        log_filepath=log_filepath,
        verbose=verbose
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
        success_msg="User vouchers retrieved successfully",
        log_filepath=log_filepath,
        verbose=verbose
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
        success_msg="Voucher redeemed successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

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

def claim_daily_bonus_rewards(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):     
    # Load rewards list
    daily_bonus_rewards = get_json_value(autoLoginUser_file, "data.daily_bonus_rewards")
    
    if not daily_bonus_rewards:
        return
    
    # Claim rewards
    for reward in daily_bonus_rewards:
        if reward["status"] == 1:
            claim_daily_bonus_reward(reward["id"], request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
def training_rewards(training):
    total = {}

    # Sum everything from rewards_star_X JSON
    for key in ["rewards_star_1", "rewards_star_2", "rewards_star_3"]:
        rewards = json.loads(training[key])
        for k, v in rewards.items():
            total[k] = total.get(k, 0) + v

    # Add explicit stat_points_star_X fields
    for key in ["stat_points_star_1", "stat_points_star_2", "stat_points_star_3"]:
        total["statPoints"] = total.get("statPoints", 0) + training.get(key, 0)

    return total

def get_best_training(autoLoginUser_file, constants_file, weights, check_energy=False, verbose=False):
    with open(constants_file, "r", encoding="utf-8") as f:
        contants_data = json.load(f)
    
    inventory = get_json_value(autoLoginUser_file, "data.inventory")
    items = get_json_value(autoLoginUser_file, "data.items")

    best_training = {
        "id": None,
        "score": 0,
        "training_cost": 999
    }

    if verbose:
        print(f"{'ID':<8} {'Cost':<8} {'Score':<15} {'Rewards':<15}")
        print("-" * 85)

    # Loop through each quest in the JSON data
    for training in get_json_value(autoLoginUser_file, "data.trainings"):
        training_id = training["id"]
        training_cost = training["training_cost"]
        rewards = training_rewards(training)
        
        if training_cost == 0:
            training_cost = 1e-6
            
        score = 0
        for key, value in rewards.items():            
            # Compute score for item upgrade
            if key == "item":
                upgrade_value = get_upgrade_value(value, autoLoginUser_file, contants_data, verbose=verbose)
                score += max(0, upgrade_value) * weights.get(("item", None), 0)
                
                if is_new_item(value, items, autoLoginUser_file):
                    score += weights[("new_item", None)]
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
                    f"{training_id:<8} {training_cost:<8.0f} {score:<15.2f} {rewards}\n"
                    f"Reward weight not defined for key={key}, value={value}"
                )
                
        # Weighted score
        score = score / (training_cost*100)
        
        if verbose:
            print(f"{training_id:<8} {training_cost:<8.0f} {score:<15.2f} {rewards}")
            
        # Skip if not enough energy
        if check_energy:
            training_energy = get_json_value(autoLoginUser_file, "data.character.training_energy")
            if training_cost > training_energy:
                continue
        
        if score > best_training["score"]:
            best_training = training.copy()
            best_training["score"] = score
    
    if verbose:
        print(f"Best Training: {best_training['id']} | Cost: {best_training['training_cost']} energy | Rewards: {training_rewards(best_training)}")
        
    return best_training

def is_there_a_worldboss_event_going_on(autoLoginUser_file):
    worldboss_event_id = get_json_value(autoLoginUser_file, "data.character.worldboss_event_id")
    worldboss_events = get_json_value(autoLoginUser_file, "data.worldboss_events")
    if worldboss_event_id == 0 or worldboss_events is None:
        return False
    
    for worldboss_event in worldboss_events:
        if worldboss_event["id"] != worldboss_event_id:
            continue
        
        status = worldboss_event["status"]
        if status != 1:
            return False
        
        worldboss_stage = worldboss_event["stage"]
        player_max_stage = get_json_value(autoLoginUser_file, "data.current_goal_values.stage_reached")
        
        if worldboss_stage > player_max_stage:
            return False
        
        server_time = get_json_value(autoLoginUser_file, "data.server_time")
        worldboss_event_ts_start = worldboss_event["ts_start"]
        worldboss_event_ts_end = worldboss_event["ts_end"]
        
        if server_time < worldboss_event_ts_start or server_time > worldboss_event_ts_end:
            return False
        
        player_level = get_json_value(autoLoginUser_file, "data.character.level")
        worldboss_event_min_level = worldboss_event["min_level"]
        worldboss_event_max_level = worldboss_event["max_level"]
        
        if player_level < worldboss_event_min_level or player_level > worldboss_event_max_level:
            return False
    return True

def get_league_opponents(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "getLeagueOpponents",
        request_file,
        body_file,
        autoLoginUser_file,
        success_msg="League opponents retrieved successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def start_league_fight(character_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "startLeagueFight",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "character_id": str(character_id),
            "use_premium": "false",
            "refresh_opponents": "true"
        },
        success_msg="League fight started successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def check_for_league_fight_complete(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "checkForLeagueFightComplete",
        request_file,
        body_file,
        autoLoginUser_file,
        success_msg="League fight completion checked successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def claim_league_fight_rewards(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "claimLeagueFightRewards",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "discard_item": "false"
        },
        success_msg="League fight rewards claimed successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def get_duel_opponents(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "getDuelOpponents",
        request_file,
        body_file,
        autoLoginUser_file,
        success_msg="Duel opponents retrieved successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def start_duel(character_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "startDuel",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "character_id": str(character_id),
            "use_premium": "false",
            "refresh_opponents": "true",
            "server_id": "pt13"
        },
        success_msg="Duel started successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def check_for_duel_complete(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "checkForDuelComplete",
        request_file,
        body_file,
        autoLoginUser_file,
        success_msg="Duel completion checked successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def claim_duel_rewards(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        "claimDuelRewards",
        request_file,
        body_file,
        autoLoginUser_file,
        custom_body={
            "discard_item": "false",
            "refresh_inventory": "true"
        },
        success_msg="Duel rewards claimed successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def start_training(best_training, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        action="startTraining",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "training_id": str(best_training["id"]),
            "refresh_trainings": "true",
        },
        success_msg="Training started successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def start_training_quest(training_quest, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        action="startTrainingQuest",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "training_quest_id": str(training_quest["id"]),
            "training_ids": "0",
        },
        success_msg="Training quest started successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def claim_training_quest_rewards(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        action="claimTrainingQuestRewards",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        success_msg="Training quest rewards claimed successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def claim_training_star(request_file, body_file, autoLoginUser_file, discard_item=False, log_filepath=None, verbose=False):
    response = perform_request(
        action="claimTrainingStar",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "discard_item": "false",
        },
        success_msg="Training star claimed successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def finish_training(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        action="finishTraining",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        success_msg="Training finished successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def sell_item_request(item_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        action="sellInventoryItem",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "item_id": str(item_id)
        },
        success_msg=f"Sold item {item_id}",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def claim_daily_bonus_reward(reward_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        action="claimDailyBonusRewardReward",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "id": str(reward_id),
            "discard_item": "false"
        },
        success_msg=f"Daily bonus reward {reward_id} claimed successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def sync_game(request_file, body_file, autoLoginUser_file, force_sync=False, log_filepath=None, verbose=False):
    response = perform_request(
        action="syncGame",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "force_sync": "true" if force_sync else "false",
        },
        success_msg="Game synced successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def refresh_training_pool(request_file, body_file, autoLoginUser_file, use_premium=False, use_free=True, log_filepath=None, verbose=False):
    response = perform_request(
        action="refreshTrainingPool",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "use_premium": "true" if use_premium else "false",
            "use_free": "true" if use_free else "false",
        },
        success_msg="Training pool refreshed successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def start_world_boss_attack(request_file, body_file, autoLoginUser_file, worldboss_event_id, iterations=1, log_filepath=None, verbose=False):
    response = perform_request(
        action="startWorldbossAttack",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "worldboss_event_id": str(worldboss_event_id),
            "iterations": str(iterations),
        },
        success_msg="World boss attack started successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )
    return response

def check_world_boss_attack_complete(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    return perform_request(
        action="checkForWorldbossAttackComplete",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        success_msg="World boss attack completion checked",
        log_filepath=log_filepath,
        verbose=verbose
    )

def finish_world_boss_attack(request_file, body_file, autoLoginUser_file, worldboss_event_id, log_filepath=None, verbose=False):
    return perform_request(
        action="finishWorldbossAttack",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "worldboss_event_id": str(worldboss_event_id),
        },
        success_msg="World boss attack finished successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )

def get_json_value(filepath, path=None, default=None):
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    if path is None:
        return data  # return full JSON
    
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
        
    # Special case: map data.item → data.items
    if path == ["data"] and isinstance(json2, dict):
        if "item" in json2:
            json2 = json2.copy()
            json2.setdefault("items", [])
            json2["items"].append(json2.pop("item"))
        if "daily_bonus_reward" in json2:
            json2 = json2.copy()
            json2.setdefault("daily_bonus_rewards", [])
            json2["daily_bonus_rewards"].append(json2.pop("daily_bonus_reward"))

    # If both are dicts → merge recursively
    if isinstance(json1, dict) and isinstance(json2, dict):
        for key, value in json2.items():
            if key in json1:
                json1[key] = merge_json(json1[key], value, path + [key])
            else:
                json1[key] = value
        return json1

    # Special case: items and daily_bonus_rewards → append lists (no duplicates by id)
    elif path in (["data", "items"], ["data", "daily_bonus_rewards"]) and isinstance(json1, list) and isinstance(json2, list):
        indexed = {item["id"]: item for item in json1}
    
        for item in json2:
            item_id = item["id"]
            if item_id in indexed:
                # merge existing item
                indexed[item_id] = merge_json(indexed[item_id], item, path + ["id"])
            else:
                indexed[item_id] = item
    
        return list(indexed.values())

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
        
def perform_request(action, request_file, body_file, autoLoginUser_file, custom_body=None, headers_override=None, success_msg=None, ignore_errors=None, max_attempts=2, log_filepath=None, verbose=False):
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
    
    ignore_errors = set(ignore_errors or [])
    
    for attempt in range(1, max_attempts + 1):
        # Send the POST request
        response = requests.post(url, headers=headers, data=encoded_body)
    
        if log_filepath:
            log_response(action, response, log_filepath)
    
        try:
            response_json = response.json()
        except ValueError:
            raise RuntimeError(f"{action} returned non-JSON response: {response.text[:200]}")
    
        if response_json["error"] == "":
            if success_msg and verbose:
                print(success_msg)
    
            with open(autoLoginUser_file, 'r') as f:
                data = json.load(f)
    
            with open(autoLoginUser_file, 'w') as f:
                json.dump(merge_json(data, response_json), f, indent=4)
                
            return response_json
        elif response_json["error"] == "errUserNotAuthorized":
            if attempt < max_attempts:
                request_user_info(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
                continue
            else:
                break
        elif response_json["error"] in ignore_errors:
            return response_json
        else:
            raise RuntimeError(f"{action} failed: {response_json['error']}")

    raise RuntimeError(f"{action} failed after {max_attempts} attempts")

def request_user_info(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
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
    
    if log_filepath:
        log_response("autoLoginUser", response, log_filepath)

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