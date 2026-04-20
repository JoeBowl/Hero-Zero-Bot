from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))


import src.tasks as tasks
import src.bot as bot
from functools import partial
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
        ("item", None): 1e3,
        ("new_item", None): 1e4,
        
        # Quest type multipliers
        ("fight", None): 0.9,
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

    task_list  = [
        tasks.Task("Quest", 
             partial(tasks.do_quest,
             defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, REWARD_WEIGHTS, CONSTANTS, COOLDOWN=COOLDOWN, log_filepath=log_filepath, verbose=True)),
        
        tasks.Task("CollectHideoutRooms", 
             partial(tasks.do_collect_hideout_rooms,
             defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, cooldown=0.75, log_filepath=log_filepath, verbose=True)),
        
        tasks.Task("LeagueDuel",
            partial(tasks.do_league_duel,
                defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath, verbose=True)),
    
        tasks.Task("Duel",
            partial(tasks.do_duel,
                defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath, verbose=True)),
    ]

    last_run_date = None
    
    while True:
        now = datetime.datetime.now()
        
        # Login once every day
        if last_run_date is None or last_run_date < now.date():
            print("Logging in")
            bot.request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, verbose=False)
            last_run_date = now.date()
                
        next_task = min(task_list, key=lambda t: t.next_available_time)

        if next_task.is_available():
            next_task.run()
        else:
            # Sleep until the next task is ready
            wait_time = (next_task.next_available_time - now).total_seconds()
            finish_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
            minutes = int(wait_time // 60)
            seconds = int(wait_time % 60)
            print(f"Waiting {wait_time // 60:.0f} min (until {finish_time.strftime('%H:%M:%S')})")
            time.sleep(wait_time)