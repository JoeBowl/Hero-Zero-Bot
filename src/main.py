from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.bot import request_user_info, get_active_quest_id, get_current_energy, get_best_quest, start_quest, check_for_quest_complete, claim_quest_rewards, buy_quest_energy
import datetime
import time

if __name__ == "__main__":
    defaultHeaders_filepath = f"{BASE_DIR}/src/defaultHeaders.txt"
    defaultBody_filepath = f"{BASE_DIR}/src/defaultBody.txt"
    autoLoginUser_filepath = f"{BASE_DIR}/src/autoLoginUser.json"
    log_filepath = f"{BASE_DIR}/src/log.txt"
    COOLDOWN = 5

    REWARD_WEIGHTS = {
        # Standard resources
        ("xp", None): 1.0,
        ("coins", None): 0.0,
        ("premium", None): 1e10,

        # Upgrade system
        ("item", None): 2e3,
        
        # Quest type multipliers
        ("fight", None): 0.1,   # higher reward for combat
        ("timer", None): 1.0,   # baseline

        # Event-specific rewards
        ("dungeon_key", None): 1e5,
        ('herobook_item_epic', None): 1e5,
        ("herobook_item_rare", None): 2e3,
        ("herobook_item_common", None): 2e3,
        ('story_dungeon_item', None): 2e3,
        ("event_item", "server_launch_blooming_nature_lotus"): 0,
        ("slotmachine_jetons", None): 1e3,
        ("event_item", 'easter_eggs'): 2e3,
        ("event_item", 'easter_bunnies'): 2e3,
        ("repeat_story_dungeon_index", None): 1e3,
    }
    
    # Constants from the game files that are needed for the buy_quest_energy function
    CONSTANTS = {
        "energy_per_refill": 50,
        "quest_max_refill_amount_per_day": 200,
        "cost_factors": [
            1800,
            6300,
            10800,
            15300,
            30600,
            45900,
            61200,
            76500
        ],
        "coins_per_time": {
            "base": 0.02,
            "scale": 0.01,
            "level_scale": 0.35,
            "level_exp": 1.55
        }
    }

    # Login
    request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, verbose=False)

    while True:
        active_quest = get_active_quest_id(autoLoginUser_filepath)

        if active_quest == 0:
            best_quest = get_best_quest(autoLoginUser_filepath, REWARD_WEIGHTS, check_energy=False, verbose=True)
            print(f"Best quest: {best_quest['id']} | Duration: {best_quest['duration']/60:.1f} min | Rewards: {best_quest['rewards']}")
            
            current_quest_energy = get_current_energy(autoLoginUser_filepath)
            print("quest_energy:", current_quest_energy)
            # break
        
            # Check if best_quest is valid
            if not best_quest or best_quest["id"] is None:
                print("No valid quest found. Breaking loop.")
                break
            elif best_quest["energy_cost"] > current_quest_energy:
                response = buy_quest_energy(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, CONSTANTS, log_filepath=log_filepath)

            # Start a quest
            response = start_quest(best_quest, defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath)
            
            wait_time = best_quest['duration'] + COOLDOWN
            finish_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
            print(f"Waiting {wait_time / 60:.0f} min (until {finish_time.strftime('%H:%M:%S')})")
            time.sleep(best_quest['duration'] + COOLDOWN)

        # Check of quest completion
        check_for_quest_complete(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, cooldown=60, log_filepath=log_filepath)
        
        # Claim quest rewards
        response = claim_quest_rewards(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath)