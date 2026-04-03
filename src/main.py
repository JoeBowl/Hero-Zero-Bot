from bot2 import *

if __name__ == "__main__":
    defaultHeaders_filepath = "src/defaultHeaders2.txt"
    defaultBody_filepath = "src/defaultBody2.txt"
    autoLoginUser_filepath = "src/autoLoginUser.json"
    log_filepath = "src/log.txt"
    COOLDOWN = 5

    REWARD_WEIGHTS = {
        # Standard resources
        ("xp", None): 1.0,
        ("coins", None): 0.1,
        ("premium", None): 1e10,

        # Upgrade system
        ("item", None): 2e3,

        # Event-specific rewards
        ("dungeon_key", None): 1e5,
        ('herobook_item_epic', None): 1e5,
        ("herobook_item_rare", None): 2e3,
        ("herobook_item_common", None): 2e3,
        ('story_dungeon_item', 'storydungeon1_4_laundry'): 2e3,
        ("event_item", "server_launch_blooming_nature_lotus"): 0,
        ("slotmachine_jetons", None): 1e3,
        ("event_item", 'easter_eggs'): 2e3,
        ("event_item", 'easter_bunnies'): 2e3,
    }

    request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, verbose=False)

    while True:
        active_quest = get_active_quest_id(autoLoginUser_filepath)

        if active_quest == 0:
            current_quest_energy = get_current_energy(autoLoginUser_filepath)
            print("quest_energy:", current_quest_energy)

            best_quest = get_best_quest(autoLoginUser_filepath, REWARD_WEIGHTS, check_energy=False, verbose=True)
            best_quest_id = str(best_quest["id"])
            print("Best quest:", best_quest["id"], best_quest["duration"]/60, best_quest["rewards"])
            
            # Check if best_quest is valid
            if not best_quest or best_quest["id"] is None:
                print("No valid quest found. Breaking loop.")
                break
            elif best_quest["energy_cost"] > current_quest_energy:
                print(f"Not enough energy for quest {best_quest['id']}. Required: {best_quest['energy_cost']}, Available: {current_quest_energy}. Breaking loop.")
                break
            break

            # Start a quest
            response = start_quest(best_quest_id, defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath)
            
            wait_time = best_quest['duration'] + COOLDOWN
            finish_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
            print(f"Waiting {wait_time / 60:.0f} min (until {finish_time.strftime('%H:%M:%S')})")
            time.sleep(best_quest['duration'] + COOLDOWN)

        # Check if quest is finished
        # If quest isn't finished yet, try again. If quest isn't finished after 5 tries, break
        start_time = time.time()
        while time.time() - start_time < 5*60:
            response = check_for_quest_complete(defaultHeaders_filepath, defaultBody_filepath, log_filepath=log_filepath)
            
            if not response['error']:  # handles None or ""
                break
            elif response['error'] == "errFinishNotYetCompleted":
                time.sleep(60)
            else:
                raise RuntimeError(f"Unexpected error: {response['error']}")
                
            time.sleep(60)

        # Claim quest rewards
        response = claim_quest_rewards(defaultHeaders_filepath, defaultBody_filepath, log_filepath=log_filepath)