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
        print(f"\n[{self.name}] Running at {datetime.datetime.now().strftime('%H:%M:%S')}")
        wait_time = self.function_to_run()
        self.next_available_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        print(f"[{self.name}] Task will be available again at {self.next_available_time.strftime('%H:%M:%S')}\n")
        return wait_time

def do_quest(request_file, body_file, autoLoginUser_file, REWARD_WEIGHTS, CONSTANTS, COOLDOWN=5, log_filepath=None, verbose=False):
    active_quest_id = bot.get_active_quest_id(autoLoginUser_file)

    if active_quest_id == 0:
        best_quest = bot.get_best_quest(autoLoginUser_file, REWARD_WEIGHTS, verbose=verbose)
            
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
        quests = bot.get_json_value(autoLoginUser_file, "data.quests")
        quest = next((q for q in quests if q.get("id") == active_quest_id), None)

        if quest is None:
            raise RuntimeError("do_quest: Quest not found")
        
        ts_complete = quest.get("ts_complete")
        ts_now = int(datetime.datetime.now().timestamp())

        if ts_complete > ts_now:
            print(f"Quest {active_quest_id} not ready yet")
            return ts_complete - ts_now

    bot.check_for_quest_complete(request_file, body_file, autoLoginUser_file, cooldown=60, log_filepath=log_filepath, verbose=verbose)
    bot.claim_quest_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    return COOLDOWN  # recheck for a new quest in COOLDOWN secs

def do_collect_hideout_rooms(request_file, body_file, autoLoginUser_file, cooldown=0.75, log_filepath=None, verbose=False):
    bot.collect_hideout_room(request_file, body_file, autoLoginUser_file, cooldown=cooldown, log_filepath=log_filepath, verbose=verbose)

    return 3600

def do_league_duel(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    league_group_id = bot.get_json_value(autoLoginUser_file, "data.character.league_group_id")
    if league_group_id == 0:
        if verbose:
            print("League duels not unlocked yet!")
        now = datetime.datetime.now()
        tomorrow = now.date() + datetime.timedelta(days=1)
        reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
        return (reset_time - now).total_seconds()

    league_fight_count = bot.get_json_value(autoLoginUser_file, "data.character.league_fight_count")
    if league_fight_count >= 24:
        if verbose:
            print("League fight limit reached")
        now = datetime.datetime.now()
        tomorrow = now.date() + datetime.timedelta(days=1)
        reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
        return (reset_time - now).total_seconds()
    
    while True:
        active_league_fight_id = bot.get_json_value(autoLoginUser_file, "data.character.active_league_fight_id")
        
        if active_league_fight_id == 0:
            league_stamina = bot.get_json_value(autoLoginUser_file, "data.character.league_stamina")
            league_stamina_cost = bot.get_json_value(autoLoginUser_file, "data.character.league_stamina_cost")
            
            if league_stamina < league_stamina_cost:
                if verbose:
                    print("Not enough league stamina")
                break
            
            candidates_weak = []
            candidates_same_team = []
            candidates_all = []
            MAX_RETRIES = 2

            for attempt in range(MAX_RETRIES + 1):  # initial try + 2 retries
                response = response = bot.get_league_opponents(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            
                if response.get("error") != "errUserNotAuthorized":
                    break
            
                if attempt < MAX_RETRIES:
                    bot.request_user_info(request_file, body_file, autoLoginUser_file, verbose=verbose)
                else:
                    raise Exception("do_duel: Authorization failed after 3 retries")
                
            opponents_in_my_guild = bot.get_league_opponents_in_my_guild(autoLoginUser_file)
            my_stats = bot.get_stats(
                bot.get_json_value(autoLoginUser_file, "data.character")
            )
            
            # Start by checking for weak characters that are not in the same guild as me
            for op in bot.get_json_value(autoLoginUser_file, "data.league_opponents"):
                op_stats = bot.get_stats(op["opponent"])
                
                is_guild = op["opponent"]["name"] in opponents_in_my_guild
                
                entry = op.copy()
                entry["stats"] = op_stats
                
                candidates_all.append(entry)
                
                if is_guild:
                    candidates_same_team.append(entry)
                elif my_stats - op_stats >= 800:
                    candidates_weak.append(entry)
                    
            if len(candidates_weak) > 0:
                selected = max(candidates_weak, key=lambda x: x["opponent"]["league_points"])
            elif candidates_same_team:
                selected = min(candidates_same_team, key=lambda x: x["stats"])
            else:
                selected = min(candidates_all, key=lambda x: x["stats"])
                
            # print(selected["opponent"]["name"])
            # print(selected["opponent"]["id"])
            # break
        
            bot.start_league_fight(selected["opponent"]["id"], request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            bot.get_league_rewards(autoLoginUser_file, verbose=True)
            time.sleep(1)
            
        bot.check_for_league_fight_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_league_fight_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        # break
    
    return 3600*2

def do_duel(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    while True:
        MAX_RETRIES = 2
        for attempt in range(MAX_RETRIES + 1):  # initial try + 2 retries
            response = bot.get_duel_opponents(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
            if response.get("error") != "errUserNotAuthorized":
                break
        
            if attempt < MAX_RETRIES:
                bot.request_user_info(request_file, body_file, autoLoginUser_file, verbose=verbose)
            else:
                raise Exception("do_duel: Authorization failed after 3 retries")
        
        active_duel_id = bot.get_json_value(autoLoginUser_file, "data.character.active_duel_id")
        
        if active_duel_id == 0:
            duel_stamina = bot.get_json_value(autoLoginUser_file, "data.character.duel_stamina")
            duel_stamina_cost = bot.get_json_value(autoLoginUser_file, "data.character.duel_stamina_cost")
            
            if duel_stamina < duel_stamina_cost:
                if verbose:
                    print("Not enough duel stamina")
                break
            
            candidates_weak = []
            candidates_same_team = []
            candidates_all = []
            opponents_in_my_guild = bot.get_duel_opponents_in_my_guild(autoLoginUser_file)
            my_stats = bot.get_stats(
                bot.get_json_value(autoLoginUser_file, "data.character")
            )
            
            # Start by checking for weak characters that are not in the same guild as me
            for op in bot.get_json_value(autoLoginUser_file, "data.opponents"):
                op_stats = bot.get_stats(op)
                
                is_guild = op["name"] in opponents_in_my_guild
                
                entry = op.copy()
                entry["stats"] = op_stats
                
                candidates_all.append(entry)
                
                if is_guild:
                    candidates_same_team.append(entry)
                elif my_stats - op_stats >= 800:
                    candidates_weak.append(entry)
                    
            if not candidates_all:
                raise RuntimeError("do_duel: No opponents available")
                    
            if len(candidates_weak) > 0:
                selected = max(candidates_weak, key=lambda x: x["honor"])
            elif candidates_same_team:
                selected = min(candidates_same_team, key=lambda x: x["stats"])
            else:
                selected = min(candidates_all, key=lambda x: x["stats"])
                
            bot.start_duel(selected["id"], request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            bot.get_duel_rewards(autoLoginUser_file, verbose=True)
            time.sleep(1)
            
        bot.check_for_duel_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_duel_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        # break
    
    return 40*60