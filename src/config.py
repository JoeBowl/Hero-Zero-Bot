COOLDOWN = 5

do_quest = True
do_duel = True
do_league_duel = True
do_collect_hideout_rooms = True
do_sell_inventory  = True

sell_common = True
sell_rare = True
sell_epic = False

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
