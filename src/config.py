COOLDOWN = 5

# Actions performed by the bot
quests                = True
train                 = True
duels                 = True
league_duels          = True
collect_hideout_rooms = True
sell_inventory        = True
world_boss            = False
claim_treasure_events = True
buy_boosters          = True
guild_battles         = False

# What to sell if sell_inventory is True
sell_common = True
sell_rare = True
sell_epic = False

REWARD_WEIGHTS = {
    # Standard resources
    ("xp", None): 1.0,
    ("coins", None): 0.0,
    ("premium", None): 1e10,
    
    # Trainings
    ("statPoints", None): 1e4,
    ("training_progress", None): 1e3,

    # Upgrade system
    ("item", None): 1e3,
    ("new_item", None): 1e4,
    
    # Quest type multipliers
    ("timer", None): 0.1,
    ("fight_difficulty_1", None): 0.96,    # easy
    ("fight_difficulty_2", None): 0.9,     # medium
    ("fight_difficulty_3", None): 0.7,     # hard

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
