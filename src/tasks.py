from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import src.bot as bot
import datetime
import time
import json

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
        print(f"[{self.name}] Task will be available again at {self.next_available_time.strftime('%H:%M:%S')}")
        return wait_time

def do_quest(request_file, body_file, autoLoginUser_file, constants_file, REWARD_WEIGHTS, COOLDOWN=5, log_filepath=None, verbose=False):
    active_quest_id = bot.get_active_quest_id(autoLoginUser_file)

    if active_quest_id == 0:
        best_quest = bot.get_best_quest(autoLoginUser_file, constants_file, REWARD_WEIGHTS, verbose=verbose)
            
        current_quest_energy = bot.get_current_energy(autoLoginUser_file)
        print("quest_energy:", current_quest_energy)

        if not best_quest or best_quest["id"] is None:
            raise RuntimeError("No valid quest found. Breaking loop.")
        elif best_quest["energy_cost"] > current_quest_energy:
            response = bot.buy_quest_energy(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
            
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
    
    # Claim daily reward, if any
    bot.claim_daily_bonus_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            
    return COOLDOWN  # recheck for a new quest in COOLDOWN secs

def do_training(request_file, body_file, autoLoginUser_file, constants_file, REWARD_WEIGHTS, log_filepath=None, verbose=False):
    training_count = bot.get_json_value(autoLoginUser_file, "data.character.training_count")
    if training_count == 0:
        now = datetime.datetime.now()
        tomorrow = now.date() + datetime.timedelta(days=1)
        reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
        return (reset_time - now).total_seconds()

    bot.sync_game(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    training_pool = bot.get_json_value(autoLoginUser_file, "data.character.training_pool")
    active_training = bot.get_json_value(autoLoginUser_file, "data.character.active_training_id")
    
    if training_pool == "" and active_training == 0:
        bot.refresh_training_pool(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)

    if active_training == 0:
        best_training = bot.get_best_training(autoLoginUser_file, constants_file, REWARD_WEIGHTS, verbose=verbose)
        
        training_count = bot.get_json_value(autoLoginUser_file, "data.character.training_count")
        print("training_count:", training_count)
        
        if not best_training or best_training["id"] is None:
            raise RuntimeError("No valid training found. Breaking loop.")
        elif best_training["training_cost"] > training_count:
            raise RuntimeError("No energy. Breaking loop.")
        bot.start_training(best_training, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.sync_game(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    training_end_time = bot.get_json_value(autoLoginUser_file, "data.training.ts_end")
    
    while True:
        current_time = int(datetime.datetime.now().timestamp())
        if current_time >= training_end_time:
            break
        current_energy = bot.get_json_value(autoLoginUser_file, "data.character.training_energy")
        future_energy = (training_end_time - current_time)//60
        total_energy = current_energy + future_energy

        total_progress = bot.get_json_value(autoLoginUser_file, "data.training.needed_energy")
        current_progress = bot.get_json_value(autoLoginUser_file, "data.training.energy")
        
        if current_progress is None:
            current_progress = 0
        if total_progress is None:
            total_progress = total_energy*10 + current_progress
    
        progress_needed = total_progress - current_progress
        
        local_weights = REWARD_WEIGHTS.copy()
        # print("energy:", total_energy, progress_needed)
        if total_energy * 10 >= progress_needed:
            local_weights[("fight", None)] = 0.1
            local_weights[("timer", None)] = 1.0
        else:
            local_weights[("fight", None)] = 1.0
            local_weights[("timer", None)] = 1.0
        
        best_training_quest = bot.get_best_quest(autoLoginUser_file, constants_file, local_weights, quest_type = "data.training_quests", max_energy=total_energy, verbose=verbose)
        time_left = training_end_time - current_time
        print(f"training_quest_energy: {current_energy} | "
              f"progress: {current_progress}/{total_progress} |"
              f"time_left: {time_left//60:02d}:{time_left%60:02d}"
        )
        
        if best_training_quest["energy_cost"] > current_energy:
            time_left_for_quest = (best_training_quest["energy_cost"] - current_energy) * 60
            time_left_for_training_end = training_end_time - current_time
            # print("time:", time_left_for_quest, time_left_for_training_end)
            return min(time_left_for_quest, time_left_for_training_end - 5)
        
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

def do_collect_hideout_rooms(request_file, body_file, autoLoginUser_file, cooldown=0.75, log_filepath=None, verbose=False):
    bot.collect_hideout_room(request_file, body_file, autoLoginUser_file, cooldown=cooldown, log_filepath=log_filepath, verbose=verbose)

    return 3600

def do_league_duel(request_file, body_file, autoLoginUser_file, COOLDOWN=7200, log_filepath=None, verbose=False):
    league_group_id = bot.get_json_value(autoLoginUser_file, "data.character.league_group_id")
    if league_group_id == 0:
        if verbose:
            print("League duels not unlocked yet!")
        now = datetime.datetime.now()
        tomorrow = now.date() + datetime.timedelta(days=1)
        reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
        return (reset_time - now).total_seconds()
    
    while True:
        league_fight_count = bot.get_json_value(autoLoginUser_file, "data.character.league_fight_count")
        if league_fight_count >= 24:
            if verbose:
                print("League fight limit reached")
            now = datetime.datetime.now()
            tomorrow = now.date() + datetime.timedelta(days=1)
            reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
            return (reset_time - now).total_seconds()
        
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
            
            bot.get_league_opponents(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            
            opponents_in_my_guild = bot.get_league_opponents_in_my_guild(autoLoginUser_file)
            my_stats = bot.get_stats(
                bot.get_json_value(autoLoginUser_file, "data.character")
            )
            
            # Start by checking for weak characters that are not in the same guild as me
            for op in bot.get_json_value(autoLoginUser_file, "data.league_opponents"):
                if op["opponent"]["name"].startswith("deleted"):
                    continue
                
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
            bot.get_league_rewards(autoLoginUser_file, verbose=verbose)
            time.sleep(1)
            
        bot.check_for_league_fight_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_league_fight_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    # Claim daily reward, if any
    bot.claim_daily_bonus_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    now = datetime.datetime.now()
    tomorrow = now.date() + datetime.timedelta(days=1)
    reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
    return min(COOLDOWN, (reset_time - now).total_seconds())

def do_duel(request_file, body_file, autoLoginUser_file, COOLDOWN=2400, log_filepath=None, verbose=False):
    while True:
        bot.get_duel_opponents(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
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
                if op["name"].startswith("deleted"):
                    continue
                
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
            bot.get_duel_rewards(autoLoginUser_file, verbose=verbose)
            time.sleep(1)
            
        bot.check_for_duel_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_duel_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    # Claim daily reward, if any
    bot.claim_daily_bonus_rewards(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    now = datetime.datetime.now()
    tomorrow = now.date() + datetime.timedelta(days=1)
    reset_time = datetime.datetime.combine(tomorrow, datetime.datetime.min.time()) + datetime.timedelta(minutes=5)
    return min(COOLDOWN, (reset_time - now).total_seconds())

def do_sell_inventory_items(request_file, body_file, autoLoginUser_file, constants_file, COOLDOWN=1800, sell_common=False, sell_rare=False, sell_epic=False, log_filepath=None, verbose=False):
    inventory = bot.get_json_value(autoLoginUser_file, "data.inventory")
    items = bot.get_json_value(autoLoginUser_file, "data.items")
    
    # Load constants data
    with open(constants_file, "r", encoding="utf-8") as f:
        contants_data = json.load(f)
    
    allowed_qualities = set()
    if sell_common:
        allowed_qualities.add(1)
    if sell_rare:
        allowed_qualities.add(2)
    if sell_epic:
        allowed_qualities.add(3)
    
    if not allowed_qualities:
        return COOLDOWN
    
    # Collect bag item IDs
    bag_item_ids = {
        value for key, value in inventory.items()
        if key.startswith("bag_item") and value not in (0, -1)
    }
    
    for item in items:
        if item["id"] not in bag_item_ids:
            continue

        if item.get("quality") not in allowed_qualities:
            continue

        # Compare against equipped
        upgrade_value = bot.get_upgrade_value(item["id"], autoLoginUser_file, contants_data, verbose=False)
        if upgrade_value >= 0:
            continue
            
        bot.sell_item_request(item["id"], request_file, body_file, autoLoginUser_file, verbose=False)
        
        if verbose:
            print(f"Sold item {item['id']} {item['identifier']} Total {upgrade_value}")
        
        time.sleep(0.2)
    
    return COOLDOWN

def fight_world_boss(request_file, body_file, autoLoginUser_file, COOLDOWN=0, log_filepath=None, verbose=False):
    if not bot.is_there_a_worldboss_event_going_on(autoLoginUser_file):
        start_times = bot.get_json_value(autoLoginUser_file, "data.event_quest.worldboss_start_times")
        
        if not start_times:
            return 3600  # fallback
        
        now = datetime.datetime.now()
        upcoming_times = []

        for entry in start_times:
            dt = datetime.datetime.strptime(entry["startDateTime"], "%Y-%m-%d %H:%M:%S")
            if dt > now:
                upcoming_times.append(dt)
                
        if not upcoming_times:
            # No more events today → wait longer (or until next refresh cycle)
            return 3600
        
        next_event = min(upcoming_times)
        wait_seconds = int((next_event - now).total_seconds())
        
        if verbose:
            print(f"Next world boss at {next_event} (in {wait_seconds}s)")

        return wait_seconds
    
    active_worldboss_attack_id = bot.get_json_value(autoLoginUser_file, "data.character.active_worldboss_attack_id")
    worldboss_event_id = bot.get_json_value(autoLoginUser_file, "data.character.worldboss_event_id")
    
    if active_worldboss_attack_id == 0:
        npc_hitpoints_current = bot.get_json_value(autoLoginUser_file, "data.worldboss_events.npc_hitpoints_current")
        npc_hitpoints_total = bot.get_json_value(autoLoginUser_file, "data.worldboss_events.npc_hitpoints_total")
        
        if npc_hitpoints_total:
            hp_percent = (npc_hitpoints_current / npc_hitpoints_total) * 100
            print(f"World Boss HP: {npc_hitpoints_current}/{npc_hitpoints_total} ({hp_percent:.2f}%)")
        else:
            print("World Boss HP: unknown")
        
        bot.start_world_boss_attack(request_file, body_file, autoLoginUser_file, worldboss_event_id, log_filepath=log_filepath, verbose=verbose)
        
        wait_time = bot.get_json_value(autoLoginUser_file, "data.worldboss_attack.duration")
        return wait_time
    else:
        ts_complete = bot.get_json_value(autoLoginUser_file, "data.worldboss_attack.ts_complete")
        ts_now = int(datetime.datetime.now().timestamp())
        
        if ts_complete > ts_now:
            print("World boss attack not ready yet")
            return ts_complete - ts_now
    
    bot.check_world_boss_attack_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    bot.finish_world_boss_attack(request_file, body_file, autoLoginUser_file, worldboss_event_id, log_filepath=log_filepath, verbose=verbose)
    
    return COOLDOWN