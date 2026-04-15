from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import src.bot as bot
import datetime
import time

class Task:
    def __init__(self, name, function_to_run, duration=0):
        self.name = name
        self.function_to_run = function_to_run
        self.next_available_time = datetime.datetime.now()
        self.duration = duration  # duration in seconds

    def is_available(self):
        return datetime.datetime.now() >= self.next_available_time

    def run(self):
        print(f"[{self.name}] Running at {datetime.datetime.now().strftime('%H:%M:%S')}")
        wait_time = self.function_to_run()
        self.next_available_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        print(f"[{self.name}] Task will be available again at {self.next_available_time.strftime('%H:%M:%S')}")
        return wait_time

def do_quest(request_file, body_file, autoLoginUser_file, REWARD_WEIGHTS, CONSTANTS, COOLDOWN=5, log_filepath=None, verbose=False):
    active_quest = bot.get_active_quest_id(autoLoginUser_file)

    if active_quest == 0:
        best_quest = bot.get_best_quest(autoLoginUser_file, REWARD_WEIGHTS, check_energy=False, verbose=verbose)
        # return 30
        # raise RuntimeError("test")
            
        current_quest_energy = bot.get_current_energy(autoLoginUser_file)
        print("quest_energy:", current_quest_energy)

        if not best_quest or best_quest["id"] is None:
            raise RuntimeError("No valid quest found. Breaking loop.")
        elif best_quest["energy_cost"] > current_quest_energy:
            response = bot.buy_quest_energy(request_file, body_file, autoLoginUser_file, CONSTANTS, log_filepath=log_filepath, verbose=verbose)
            
            if response["error"] == "refillLimitReached":
                now = datetime.datetime.now()
                tomorrow = now.date() + datetime.timedelta(days=1)
                reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
                return (reset_time - now).total_seconds()

        response = bot.start_quest(best_quest, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
        wait_time = best_quest['duration'] + COOLDOWN
        return wait_time
    else:
        bot.check_for_quest_complete(request_file, body_file, autoLoginUser_file, cooldown=60, log_filepath=log_filepath)
        bot.claim_quest_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath)
        return 5  # recheck in 5 secs

def do_collect_hideout_rooms(request_file, body_file, autoLoginUser_file, cooldown=0.75, log_filepath=None, verbose=False):
    collected = bot.collect_hideout_room(request_file, body_file, autoLoginUser_file, cooldown=cooldown, log_filepath=log_filepath, verbose=verbose)

    return 3600