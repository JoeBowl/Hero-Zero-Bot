from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import src.config as config
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

def do_quest(request_file, body_file, autoLoginUser_file, constants_file, REWARD_WEIGHTS, log_filepath=None, verbose=False):
    active_quest_id = bot.get_active_quest_id(autoLoginUser_file)
    active_duel_id = bot.get_json_value(autoLoginUser_file, "data.character.active_duel_id")
    
    if active_duel_id != 0:
        return config.TIMERS["WAIT_AFTER_DUEL_CONFLICT"]

    if active_quest_id == 0:
        best_quest = bot.get_best_quest(autoLoginUser_file, constants_file, REWARD_WEIGHTS, verbose=verbose)
            
        current_quest_energy = bot.get_current_energy(autoLoginUser_file)
        print("quest_energy:", current_quest_energy)

        if not best_quest or best_quest["id"] is None:
            raise RuntimeError("No valid quest found. Breaking loop.")
        elif best_quest["energy_cost"] > current_quest_energy:
            response = bot.buy_quest_energy(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
            
            if response["error"] == "refillLimitReached":
                return bot.time_until_daily_reset()

        response = bot.start_quest(best_quest, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
        return best_quest['duration'] + config.TIMERS["QUEST_RECHECK"]
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

    bot.check_for_quest_complete(request_file, body_file, autoLoginUser_file, cooldown=config.TIMERS["CHECK_QUEST_COMPLETE"], log_filepath=log_filepath, verbose=verbose)
    bot.claim_with_inventory_retry(bot.claim_quest_rewards, request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
    
    bot.claim_daily_bonus_rewards(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
            
    return config.TIMERS["QUEST_RECHECK"]

def do_training(request_file, body_file, autoLoginUser_file, constants_file, REWARD_WEIGHTS, log_filepath=None, verbose=False):
    bot.sync_game(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)

    training_pool = bot.get_json_value(autoLoginUser_file, "data.character.training_pool")
    active_training_id = bot.get_json_value(autoLoginUser_file, "data.character.active_training_id")

    if active_training_id == 0:
        training_count = bot.get_json_value(autoLoginUser_file, "data.character.training_count")
        if training_count == 0:
            return bot.time_until_daily_reset()

        # If not 10 mins have passed since last training, wait a bit
        ts_last_training_finished = bot.get_json_value(autoLoginUser_file, "data.character.ts_last_training_finished")
        current_time = int(datetime.datetime.now().timestamp())
        wait_seconds = ts_last_training_finished + config.TIMERS["TRAINING_FINISH_COOLDOWN"] - current_time  # 600 = 10 minutes

        if wait_seconds > 0:
            return wait_seconds
        
        if training_pool == "":
            bot.refresh_training_pool(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)

        best_training = bot.get_best_training(autoLoginUser_file, constants_file, REWARD_WEIGHTS, verbose=verbose)
        
        training_count = bot.get_json_value(autoLoginUser_file, "data.character.training_count")
        print("training_count:", training_count)
        
        if not best_training or best_training["id"] is None:
            raise RuntimeError("No valid training found. Breaking loop.")
        elif best_training["training_cost"] > training_count:
            raise RuntimeError("No energy. Breaking loop.")
        bot.start_training(best_training, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    training_end_time = bot.get_json_value(autoLoginUser_file, "data.training.ts_end")
    total_progress = bot.get_json_value(autoLoginUser_file, "data.training.needed_energy")

    if total_progress is None:
        training_id = bot.get_json_value(autoLoginUser_file, "data.training.id")
        trainings = bot.get_json_value(autoLoginUser_file, "data.trainings")

        total_progress = next(
            (t["needed_energy"] for t in trainings if t["id"] == training_id),
            None
        )

    while True:
        training_quest_id = bot.get_json_value(autoLoginUser_file, "data.training.training_quest_id")
        if training_quest_id == 0 or training_quest_id == None:
            
            current_time = int(datetime.datetime.now().timestamp())
            if current_time >= training_end_time:
                break

            current_energy = bot.get_json_value(autoLoginUser_file, "data.character.training_energy")
            future_energy = (training_end_time - current_time)//60
            total_energy = current_energy + future_energy

            current_progress = bot.get_json_value(autoLoginUser_file, "data.training.energy")
            if current_progress is None:
                current_progress = 0
        
            progress_needed = total_progress - current_progress
            
            local_weights = REWARD_WEIGHTS.copy()
            # print("energy:", total_energy, progress_needed)
            if total_energy * 10 >= progress_needed:
                local_weights[("timer", None)] = 1.0
                local_weights[("fight_difficulty_1", None)] = 0.1
                local_weights[("fight_difficulty_2", None)] = 0.1
                local_weights[("fight_difficulty_3", None)] = 0.1
            else:
                local_weights[("timer", None)] = 1.0
                local_weights[("fight_difficulty_1", None)] = 1.0
                local_weights[("fight_difficulty_2", None)] = 1.0
                local_weights[("fight_difficulty_3", None)] = 1.0
            
            best_training_quest = bot.get_best_quest(autoLoginUser_file, constants_file, local_weights, quest_type = "data.training_quests", max_energy=total_energy, verbose=verbose)
            time_left = training_end_time - current_time
            print(f"training_quest_energy: {current_energy} | "
                f"progress: {current_progress}/{total_progress} |"
                f"time_left: {time_left//60:02d}:{time_left%60:02d}"
            )
            
            if best_training_quest["energy_cost"] > current_energy:
                time_left_for_quest = (best_training_quest["energy_cost"] - current_energy) * 60
                time_left_for_training_end = training_end_time - current_time
                return min(time_left_for_quest, time_left_for_training_end + 5) # TODO
            
            bot.start_training_quest(best_training_quest, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_with_inventory_retry(bot.claim_training_quest_rewards, request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
        
        training_stars_thresholds = [0.1, 0.4, 1.0]
        new_current_energy = bot.get_json_value(autoLoginUser_file, "data.character.training_energy")
        new_current_progress = bot.get_json_value(autoLoginUser_file, "data.training.energy")
        print(f"training_quest_energy: {new_current_energy} | "
            f"progress: {new_current_progress}/{total_progress} |"
            f"time_left: {time_left//60:02d}:{time_left%60:02d}"
        )
        
        for t in training_stars_thresholds:
            if current_progress < t * total_progress and new_current_progress >= t * total_progress:
                bot.claim_with_inventory_retry(bot.claim_training_star, request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
        
        if new_current_progress >= total_progress:
            break
    
    bot.finish_training(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    return config.TIMERS["TRAINING_FINISH_COOLDOWN"]

def do_collect_hideout_rooms(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    COOLDOWN = config.TIMERS["HIDEOUT_COLLECTION_RATE"]
    bot.collect_hideout_room(request_file, body_file, autoLoginUser_file, cooldown=COOLDOWN, log_filepath=log_filepath, verbose=verbose)

    return config.TIMERS["HIDEOUT_COOLDOWN"]

def do_league_duel(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=None, verbose=False):
    league_group_id = bot.get_json_value(autoLoginUser_file, "data.character.league_group_id")
    if league_group_id == 0:
        if verbose:
            print("League duels not unlocked yet!")
        return bot.time_until_daily_reset()
    
    while True:
        league_fight_count = bot.get_json_value(autoLoginUser_file, "data.character.league_fight_count")
        if league_fight_count >= 24:
            if verbose:
                print("League fight limit reached")
            return bot.time_until_daily_reset()
        
        active_league_fight_id = bot.get_json_value(autoLoginUser_file, "data.character.active_league_fight_id")
        
        if active_league_fight_id == 0:
            league_stamina = bot.get_json_value(autoLoginUser_file, "data.character.league_stamina")
            league_stamina_cost = bot.get_json_value(autoLoginUser_file, "data.character.league_stamina_cost")
            
            if league_stamina < league_stamina_cost:
                if verbose:
                    print("Not enough league stamina")
                break
            
            bot.get_league_opponents(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            
            league_opponents_raw  = bot.get_json_value(autoLoginUser_file, "data.league_opponents").copy()
            opponents = [op["opponent"] for op in league_opponents_raw]
            
            while opponents:
                selected = bot.get_best_duel_opponent(autoLoginUser_file, opponents, reward_key="league_points")

                if not selected:
                    raise RuntimeError("No valid opponents available")
            
                bot.start_league_fight(selected["id"], request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            
                # if response.get("error") == "errStartDuelAttackCurrentlyNotAllowed":
                #     # Remove this opponent and retry
                #     opponents = [
                #         op for op in opponents
                #         if op["id"] != selected["id"]
                #     ]
                #     continue
            
                # Success
                break
            
            bot.print_league_rewards(autoLoginUser_file, verbose=verbose)
            time.sleep(config.TIMERS["BETWEEN_FIGHTS_COOLDOWN"])
        
        # TODO: If the fight started, was checked, but wasn't claimed, it will throw an error if it's checked again
        bot.check_for_league_fight_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_with_inventory_retry(bot.claim_league_fight_rewards, request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
    
    bot.claim_daily_bonus_rewards(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
    
    return min(config.TIMERS["LEAGUE_DUEL_COOLDOWN"], bot.time_until_daily_reset())

def do_duel(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=None, verbose=False):
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
            
            opponents = bot.get_json_value(autoLoginUser_file, "data.opponents").copy()
            
            while opponents:
                selected = bot.get_best_duel_opponent(autoLoginUser_file, opponents, reward_key="honor")

                if not selected:
                    raise RuntimeError("No valid opponents available")
            
                response = bot.start_duel(selected["id"], request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
            
                if response.get("error") == "errStartDuelAttackCurrentlyNotAllowed":
                    # Remove this opponent and retry
                    opponents = [
                        op for op in opponents
                        if op["id"] != selected["id"]
                    ]
                    continue
                break
                
            bot.print_duel_rewards(autoLoginUser_file, verbose=verbose)
            time.sleep(config.TIMERS["BETWEEN_FIGHTS_COOLDOWN"])
            
        bot.check_for_duel_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        bot.claim_with_inventory_retry(bot.claim_duel_rewards, request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
    
    bot.claim_daily_bonus_rewards(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=log_filepath, verbose=verbose)
    
    return min(config.TIMERS["DUEL_COOLDOWN"], bot.time_until_daily_reset())

def do_sell_inventory_items(request_file, body_file, autoLoginUser_file, constants_file, sell_common=False, sell_rare=False, sell_epic=False, log_filepath=None, verbose=False):
    COOLDOWN = config.TIMERS["SELL_INVENTORY_COOLDOWN"]
    return bot.sell_inventory_items(request_file, body_file, autoLoginUser_file, constants_file, COOLDOWN=COOLDOWN,
                                    sell_common=sell_common, sell_rare=sell_rare, sell_epic=sell_epic, log_filepath=log_filepath, verbose=verbose)

def do_fight_world_boss(request_file, body_file, autoLoginUser_file, COOLDOWN=0, log_filepath=None, verbose=False):
    if not bot.is_there_a_worldboss_event_going_on(autoLoginUser_file):
        start_times = bot.get_json_value(autoLoginUser_file, "data.event_quest.worldboss_start_times")
        
        if not start_times:
            return config.TIMERS["FALLBACK_TIMER"]
        
        now = datetime.datetime.now()
        upcoming_times = []

        for entry in start_times:
            dt = datetime.datetime.strptime(entry["startDateTime"], "%Y-%m-%d %H:%M:%S")
            if dt > now:
                upcoming_times.append(dt)
                
        if not upcoming_times:
            # No more events today → wait longer (or until next refresh cycle)
            return min(config.TIMERS["FALLBACK_TIMER"], bot.time_until_daily_reset())
        
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
        
        return bot.get_json_value(autoLoginUser_file, "data.worldboss_attack.duration") + config.TIMERS["QUEST_RECHECK"]
    else:
        ts_complete = bot.get_json_value(autoLoginUser_file, "data.worldboss_attack.ts_complete")
        ts_now = int(datetime.datetime.now().timestamp())
        
        if ts_complete > ts_now:
            print("World boss attack not ready yet")
            return ts_complete - ts_now + config.TIMERS["QUEST_RECHECK"]
    
    bot.check_world_boss_attack_complete(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    bot.finish_world_boss_attack(request_file, body_file, autoLoginUser_file, worldboss_event_id, log_filepath=log_filepath, verbose=verbose)
    
    return config.TIMERS["QUEST_RECHECK"]

def do_claim_free_treasure_revel_items(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=False):
    treasure_event_id = bot.get_json_value(autoLoginUser_file, "data.character.treasure_event_id")
    treasure_event = bot.get_json_value(autoLoginUser_file, "data.treasure_event")
    
    if not treasure_event:
        return bot.time_until_daily_reset()
    
    if treasure_event_id == 0:
        start_date = datetime.datetime.strptime(treasure_event["start_date"], "%Y-%m-%d %H:%M:%S")
        end_date = datetime.datetime.strptime(treasure_event["end_date"], "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        
        # Event is currently active
        if start_date <= now <= end_date:
            identifier = treasure_event["identifier"]
            bot.assign_treasure_event(identifier, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
        # Event has not started yet
        elif now < start_date:
            seconds_until_start = int((start_date - now).total_seconds())
            return seconds_until_start
        
        # Event already ended
        else:
            return bot.time_until_daily_reset()
        
    current_time = int(datetime.datetime.now().timestamp())
    ts_reveal_item_collected = bot.get_json_value(autoLoginUser_file, "data.treasure_event.ts_reveal_item_collected", 0)
    
    wait_time = (ts_reveal_item_collected + config.TIMERS["TREASURE_EVENT_COOLDOWN"]) - current_time
    if wait_time > 0:
        return wait_time
    
    response = bot.claim_free_treasure_reveal_items(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    if response["error"] == "errClaimFreeTreasureRevealItemsCooldownActive":
        return config.TIMERS["TREASURE_EVENT_CHECK_RETRY"]
    
    return config.TIMERS["TREASURE_EVENT_COOLDOWN"]

def do_buy_boosters(request_file, body_file, autoLoginUser_file, log_filepath=None, verbose=None):
    ts_active_quest_boost_expires = bot.get_json_value(autoLoginUser_file, "data.character.ts_active_quest_boost_expires")
    ts_active_stats_boost_expires = bot.get_json_value(autoLoginUser_file, "data.character.ts_active_stats_boost_expires")
    ts_active_work_boost_expires = bot.get_json_value(autoLoginUser_file, "data.character.ts_active_work_boost_expires")
    ts_active_league_boost_expires = bot.get_json_value(autoLoginUser_file, "data.character.ts_active_league_boost_expires")
    ts_now = int(datetime.datetime.now().timestamp()) 
    
    # Check quest boost
    if ts_active_quest_boost_expires is not None:
        if ts_active_quest_boost_expires <= ts_now + config.TIMERS["BOOSTER_BUFFER"]:
            bot.buy_booster("buyBooster", "booster_quest2", "345600", request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    # Check stats boost
    if ts_active_stats_boost_expires is not None:
        if ts_active_stats_boost_expires <= ts_now + config.TIMERS["BOOSTER_BUFFER"]:
            bot.buy_booster("buyBooster", "booster_stats2", "345600", request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    # Check work boost
    if ts_active_work_boost_expires is not None:
        if ts_active_work_boost_expires <= ts_now + config.TIMERS["BOOSTER_BUFFER"]:
            bot.buy_booster("buyBooster", "booster_work2", "345600", request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    # Check league boost
    if ts_active_league_boost_expires is not None:
        if ts_active_league_boost_expires <= ts_now + config.TIMERS["BOOSTER_BUFFER"]:
            bot.buy_booster("buyLeagueBooster", "booster_league1", "345600", request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    return bot.time_until_daily_reset()

def do_check_guild_battles(request_file, body_file, autoLoginUser_file, constants_file, log_filepath=None, verbose=False):
    bot.sync_game(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    finished_attack_id = bot.get_json_value(autoLoginUser_file, "data.character.finished_guild_battle_attack_id", 0)
    finished_defense_id = bot.get_json_value(autoLoginUser_file, "data.character.finished_guild_battle_defense_id", 0)
    finished_dungeon_id = bot.get_json_value(autoLoginUser_file, "data.character.finished_guild_dungeon_battle_id", 0)
    
    if finished_attack_id:
        bot.claim_with_inventory_retry(bot.claim_guild_battle_reward, finished_attack_id, request_file, body_file, autoLoginUser_file, constants_file=constants_file, log_filepath=log_filepath, verbose=verbose)
    
    if finished_defense_id:
        bot.claim_with_inventory_retry(bot.claim_guild_battle_reward, finished_defense_id, request_file, body_file, autoLoginUser_file, constants_file=constants_file, log_filepath=log_filepath, verbose=verbose)
    
    if finished_dungeon_id:
        bot.claim_with_inventory_retry(bot.claim_guild_dungeon_battle_reward, finished_dungeon_id, request_file, body_file, autoLoginUser_file, constants_file=constants_file, log_filepath=log_filepath, verbose=verbose)
        
    my_character_id = bot.get_json_value(autoLoginUser_file, "data.character.id", 0)
    
    pending_attack_id = bot.get_json_value(autoLoginUser_file, "data.guild.pending_guild_battle_attack_id", 0)
    pending_defense_id = bot.get_json_value(autoLoginUser_file, "data.guild.pending_guild_battle_defense_id", 0)
    pending_dungeon_id = bot.get_json_value(autoLoginUser_file, "data.guild.pending_guild_dungeon_battle_attack_id", 0)

    pending_attack_character_ids = json.loads(bot.get_json_value(autoLoginUser_file, "data.pending_guild_battle_attack.character_ids", "[]"))
    pending_defense_character_ids = json.loads(bot.get_json_value(autoLoginUser_file, "data.pending_guild_battle_defense.character_ids", "[]"))
    pending_dungeon_character_ids = json.loads(bot.get_json_value(autoLoginUser_file, "data.pending_guild_dungeon_battle.character_ids", "[]"))

    if pending_attack_id and not my_character_id in pending_attack_character_ids:
        bot.join_guild_battle(True, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    if pending_defense_id and not my_character_id in pending_defense_character_ids:
        bot.join_guild_battle(False, request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
    
    if pending_dungeon_id and not my_character_id in pending_dungeon_character_ids:
        bot.join_guild_dungeon_battle(request_file, body_file, autoLoginUser_file, log_filepath=log_filepath, verbose=verbose)
        
    return config.TIMERS["GUILD_BATTLES_COOLDOWN"]