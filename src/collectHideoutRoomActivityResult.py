from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import src.bot as bot
        
if __name__ == "__main__":
    defaultHeaders_filepath = f"{BASE_DIR}/src/defaultHeaders.txt"
    defaultBody_filepath = f"{BASE_DIR}/src/defaultBody.txt"
    autoLoginUser_filepath = f"{BASE_DIR}/src/autoLoginUser.json"
    log_filepath = f"{BASE_DIR}/src/log.txt"
    
    bot.request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, verbose=False)

    bot.collect_hideout_room(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath)