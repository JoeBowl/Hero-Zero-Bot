from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import json
from src.bot import perform_request, get_json_value, get_upgrade_value

def def_is_training_available(autoLoginUser_file):
    if get_json_value(autoLoginUser_file, "data.character.training_pool") == "":
        return False
    else:
        return True

def get_current_training_energy(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["training_energy"]

def get_active_training_id(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)

    return data["data"]["character"]["active_quest_id"]

def get_traing_time_left(autoLoginUser_file):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)
        
    server_time = data["data"]["server_time"]
    training_end_time = data["data"]["training"]["ts_end"]
    
    return training_end_time - server_time

def start_training(training_id, request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    response = perform_request(
        action="startTraining",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "training_id": str(training_id),
            "refresh_trainings": "true",
        },
        success_msg="Training started successfully" if verbose else None,
        log_filepath=log_filepath
    )
    return response

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

def get_best_training(autoLoginUser_file, weights, verbose=False):
    with open(autoLoginUser_file, 'r') as file:
        data = json.load(file)
    
    inventory = data["data"]["inventory"]
    items = data["data"]["items"]

    best_training = {
        "id": None,
        "duration": 0,
        "rewards": "{\"coins\":0,\"xp\":0}",
        "score": 0
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
        training_energy = get_json_value(autoLoginUser_file, "data.character.training_energy")
        if training_cost > training_energy:
            continue
        
        if score > best_training["score"]:
            best_training = training.copy()
            best_training["score"] = score
    
    if verbose:
        print(f"Best Training: {best_training['id']} | Cost: {best_training['training_cost']} energy | Rewards: {training_rewards(best_training)}")
        
    return best_training
        
def do_training(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    trainings = get_json_value(autoLoginUser_file, "data.trainings")
    training_energy = get_json_value(autoLoginUser_file, "data.character.training_energy")
    
    print(training_energy)
    
    for training in trainings:
        print(training)
        training_rewards(training)

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
        ("statPoints", None): 1e4,

        # Upgrade system
        ("item", None): 1e3,
        
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
    
    # do_training(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath, verbose=True)
    
    get_best_training(autoLoginUser_filepath, REWARD_WEIGHTS, verbose=True)