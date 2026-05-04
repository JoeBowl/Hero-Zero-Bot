from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))


import src.config as config
import src.tasks as tasks
import src.bot as bot
from functools import partial
import datetime
import json
import time

def extract_event_tower(autoLoginUser_file, event_id="sci_fi_week_towerevent"):
    event = bot.get_json_value(autoLoginUser_file, f"data.tower_event_data.events.events_data.{event_id}")
    tower = event["tower_data"]

    return {
        "tower_id": tower["id"],
        "tower_data": {
            "idle_income_per_sec": tower["idle_income_per_sec"],
            "vault": tower["vault"],
            "elevator": tower["elevator"],
            "regions": tower["regions"],
            "floors": tower["floors"],
            "manager_pool": tower["manager_pool"],
            "tutorial_step": tower["tutorial_step"],
            "max_floor_index": tower["max_floor_index"],
        },
        "economy_data": [
            {
                "id": tower["areas"][0]["id"],
                "bank_amount": tower["areas"][0]["bank_amount"]
            }
        ]
    }

def sync_tower_event(request_file, body_file, autoLoginUser_file,
                     tower_id, tower_data, economy_data,
                     log_filepath=None, verbose=False):

    response = bot.perform_request(
        action="syncTowerEvent",
        request_file=request_file,
        body_file=body_file,
        autoLoginUser_file=autoLoginUser_file,
        custom_body={
            "tower_id": tower_id,  # or pass as parameter if dynamic
            "tower_data": json.dumps(tower_data),
            "economy_data": json.dumps(economy_data),
        },
        success_msg="Tower event synced successfully",
        log_filepath=log_filepath,
        verbose=verbose
    )

    return response

if __name__ == "__main__":
    defaultHeaders_filepath = f"{BASE_DIR}/src/defaultHeaders2.txt"
    defaultBody_filepath = f"{BASE_DIR}/src/defaultBody2.txt"
    autoLoginUser_filepath = f"{BASE_DIR}/src/autoLoginUser2.json"
    log_filepath = f"{BASE_DIR}/src/log.txt"
    contants_filepath = f"{BASE_DIR}/src/constants.json"
    config_filepath = f"{BASE_DIR}/src/config.py"

    bot.request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath, verbose=False)

    data = extract_event_tower(autoLoginUser_filepath)
    
    tower_id = data["tower_id"]
    tower_data = data["tower_data"]
    economy_data = data["economy_data"]
    
    # M  = 1e6
    # B  = 1e9
    # T  = 1e12
    # aa = 1e15
    # ab = 1e18
    # ac = 1e21
    # ad = 1e24
    # ae = 1e27
    # af = 1e30
    # ag = 1e33
    # ah = 1e36
    print("before:", economy_data)
    economy_data[0]["bank_amount"] += 100e36
    print("after:", economy_data)

    response = sync_tower_event(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath,
                     tower_id, tower_data, economy_data,
                     log_filepath=log_filepath, verbose=True)