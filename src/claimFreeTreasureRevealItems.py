from src.bot import request_user_info, claim_free_treasure_reveal_items
import datetime
import time

if __name__ == "__main__":
    defaultHeaders_filepath = "src/defaultHeaders.txt"
    defaultBody_filepath = "src/defaultBody.txt"
    autoLoginUser_filepath = "src/autoLoginUser.json"
    log_filepath = "src/log.txt"
    
    while True:    
        wait_time = 3*3600+60*5
        finish_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        print(f"Waiting {wait_time / 60:.0f} min (until {finish_time.strftime('%H:%M:%S')})")
        time.sleep(wait_time)

        request_user_info(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, verbose=False)

        claim_free_treasure_reveal_items(defaultHeaders_filepath, defaultBody_filepath, autoLoginUser_filepath, log_filepath=log_filepath)