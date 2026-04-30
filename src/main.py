from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))


import src.config as config
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
    contants_filepath = f"{BASE_DIR}/src/constants.json"
    config_filepath = f"{BASE_DIR}/src/config.py"

    COOLDOWN = config.COOLDOWN
    
    task_list  = [
        tasks.Task("Quest", 
            partial(tasks.do_quest,
                defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, contants_filepath, 
                config.REWARD_WEIGHTS, COOLDOWN=COOLDOWN, log_filepath=log_filepath, verbose=True)) if config.do_quest else None,
        
        tasks.Task("Duel",
            partial(tasks.do_duel,
                defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, 
                log_filepath=log_filepath, verbose=True)) if config.do_duel else None,

        tasks.Task("LeagueDuel",
            partial(tasks.do_league_duel,
                defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, 
                log_filepath=log_filepath, verbose=True)) if config.do_league_duel else None,

        tasks.Task("CollectHideoutRooms", 
            partial(tasks.do_collect_hideout_rooms,
                defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, 
                cooldown=0.75, log_filepath=log_filepath, verbose=True)) if config.do_collect_hideout_rooms else None,
        
        tasks.Task("SellInventory",
            partial(tasks.do_sell_worse_inventory_items,
                defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, contants_filepath,
                sell_common=config.sell_common, sell_rare=config.sell_rare, sell_epic=config.sell_epic, 
                log_filepath=log_filepath, verbose=True)) if config.do_sell_inventory else None,
    ]
    task_list = [t for t in task_list if t is not None]

    last_run_date = None
    
    while True:
        now = datetime.datetime.now()
        
        # Login once every day
        if last_run_date is None or last_run_date < now.date():
            print("Logging in")
            bot.request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath, verbose=False)
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
            
            print("\nTask schedule:")
            for task in sorted(task_list, key=lambda t: t.next_available_time):
                ready_in = (task.next_available_time - now).total_seconds()
                
                if ready_in <= 0:
                    status = "READY"
                else:
                    minutes = int(ready_in // 60)
                    seconds = int(ready_in % 60)
                    status = f"in {minutes}m {seconds}s"

                ready_at = task.next_available_time.strftime('%H:%M:%S')
                print(f"  - {task.name}: {status} (at {ready_at})")
            
            print(f"\nNext task: {next_task.name} (at {next_task.next_available_time:%H:%M:%S})")
            time.sleep(wait_time)