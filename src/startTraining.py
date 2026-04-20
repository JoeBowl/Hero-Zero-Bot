from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import datetime
import json
import time
from src.bot import perform_request, get_json_value, get_upgrade_value, is_new_item, get_best_quest
import src.bot as bot

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

def get_best_training(autoLoginUser_file, weights, check_energy=False, verbose=False):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)
    
    inventory = data["data"]["inventory"]
    items = data["data"]["items"]

    best_training = {
        "id": None,
        "duration": 0,
        "rewards": "{\"coins\":0,\"xp\":0}",
        "score": 0,
        "energy_cost": 999
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
                upgrade_value = get_upgrade_value(value, inventory, items)
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

def get_best_training_quest(autoLoginUser_file, weights, max_energy=1e10, verbose=False):
    inventory = get_json_value(autoLoginUser_file, "data.inventory")
    items = get_json_value(autoLoginUser_file, "data.items")
    
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
    for quest in get_json_value(autoLoginUser_file, "data.training_quests"):
        quest_id = quest["id"]
        quest_cost = quest["energy_cost"]
        rewards = json.loads(quest["rewards"])
        
        if quest_cost == 0:
            quest_cost = 1e-6
            
        score = 0
        for key, value in rewards.items():            
            # Compute score for item upgrade and new item
            if key == "item":
                upgrade_value = get_upgrade_value(value, inventory, items)
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
        
def do_training(request_file, body_file, autoLoginUser_file, REWARD_WEIGHTS, log_filepath=None, verbose=False):
    bot.sync_game(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath, verbose=True)
    active_training = get_json_value(autoLoginUser_file, "data.character.active_training_id")
    
    if active_training == 0:
        best_training = get_best_training(autoLoginUser_file, REWARD_WEIGHTS, verbose=verbose)
        
        training_count = get_json_value(autoLoginUser_file, "data.character.training_count")
        print("training_count:", training_count)
        
        if not best_training or best_training["id"] is None:
            raise RuntimeError("No valid training found. Breaking loop.")
        elif best_training["training_cost"] > training_count:
            raise RuntimeError("No energy. Breaking loop.")
        
        response = bot.start_training(best_training, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.sync_game(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
    current_time = int(datetime.datetime.now().timestamp())
    training_end_time = get_json_value(autoLoginUser_file, "data.training.ts_end")
    
    while current_time < training_end_time:
        current_energy = get_json_value(autoLoginUser_file, "data.character.training_energy")
        future_energy = (training_end_time - current_time)//60

        total_progress = get_json_value(autoLoginUser_file, "data.training.needed_energy")
        current_progress = get_json_value(autoLoginUser_file, "data.training.energy")
        progress_needed = total_progress - current_progress
        
        total_energy = current_energy + future_energy
        
        local_weights = REWARD_WEIGHTS.copy()
        print("energy:", total_energy, progress_needed)
        if total_energy * 10 >= progress_needed:
            local_weights[("fight", None)] = 0.1
            local_weights[("timer", None)] = 1.0
        else:
            local_weights[("fight", None)] = 1.0
            local_weights[("timer", None)] = 1.0
        
        best_training_quest = get_best_quest(autoLoginUser_file, local_weights, quest_type = "data.training_quests", max_energy=total_energy, verbose=verbose)
        print("training_quest_energy:", current_energy)
        
        if best_training_quest["energy_cost"] > current_energy:
            time_left_for_quest = (best_training_quest["energy_cost"] - current_energy) * 60
            time_left_for_training_end = training_end_time - current_time
            print("time:", time_left_for_quest, time_left_for_training_end)
            return min(time_left_for_quest, time_left_for_training_end)
        
        bot.start_training_quest(best_training_quest, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_training_quest_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
        training_stars_thresholds = [0.1, 0.4, 1.0]
        reward_value = json.loads(best_training_quest["rewards"])["training_progress"]
        print("progress:", current_progress, current_progress+reward_value, total_progress, current_progress/total_progress, (current_progress+reward_value)/total_progress)
        for t in training_stars_thresholds:
            if current_progress < t * total_progress and current_progress + reward_value >= t * total_progress:
                bot.claim_training_star(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
        if current_progress+reward_value > total_progress:
            break
    
    bot.finish_training(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    return 60*10
    
if __name__ == "__main__":
    defaultHeaders_filepath = f"{BASE_DIR}/src/defaultHeaders.txt"
    defaultBody_filepath = f"{BASE_DIR}/src/defaultBody.txt"
    autoLoginUser_filepath = f"{BASE_DIR}/src/autoLoginUser.json"
    log_filepath = f"{BASE_DIR}/src/log.txt"
    
    REWARD_WEIGHTS = {
        # Standard resources
        ("xp", None): 1.0,
        ("coins", None): 0.0,
        ("premium", None): 1e10,
        
        # Trainings
        ("statPoints", None): 1e4,
        ("training_progress", None): 1e3,

        # Items
        ("item", None): 1e3,
        ("new_item", None): 1e4,
        
        # Quest type multipliers
        ("fight", None): 0.1,
        ("timer", None): 1.0,

        # Event-specific rewards
        ("dungeon_key", None): 2e3,
        ('story_dungeon_item', None): 2e3,
        ("repeat_story_dungeon_index", None): 2e3,
        ('herobook_item_epic', None): 1e5,
        ("herobook_item_rare", None): 1e4,
        ("herobook_item_common", None): 1e4,
        ("slotmachine_jetons", None): 1e3,
        # ("event_item", 'sun_moon_stars_season_arc_event_2024_item'): 2e3,
        # ("event_item", "server_launch_blooming_nature_lotus"): 2e3,
        # ("event_item", 'easter_eggs'): 2e3,
        # ("event_item", 'easter_bunnies'): 2e3,
        ("event_item", None): 2e3,
    }
    
    bot.request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath, verbose=False)
    while True:
        wait_time = do_training(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, REWARD_WEIGHTS, log_filepath=log_filepath, verbose=True)
        next_available_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        print(f"Task will be available again at {next_available_time.strftime('%H:%M:%S')}")
        time.sleep(wait_time)
        # sync_game(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)