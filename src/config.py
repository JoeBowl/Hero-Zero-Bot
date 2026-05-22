COOLDOWN = 5

# Actions performed by the bot
quests                = True
train                 = True
duels                 = True
league_duels          = True
collect_hideout_rooms = True
sell_inventory        = True
world_boss            = False
claim_treasure_event  = True
solve_treasure_event  = True
buy_boosters          = False
guild_battles         = True

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

# Timers - all values in seconds unless specified otherwise
TIMERS = {
    # Quest-related timers
    "QUEST_RECHECK": 1,                      # Y Recheck for new quest after completion
    "WAIT_AFTER_DUEL_CONFLICT": 60,          # Y Wait if duel is active when checking quests
    "CHECK_QUEST_COMPLETE": 60,              # Y Cooldown when checking quest completion
    
    # Training-related timers
    "TRAINING_FINISH_COOLDOWN": 600,         # Y 10 minutes - cooldown after training finishes
    
    # Hideout timers
    "HIDEOUT_COLLECTION_RATE": 0.2,          # Y Seconds between hideout room collections
    "HIDEOUT_COOLDOWN": 1800,                # Y 30 minutes - hideout collection task cooldown
    
    # PvP cooldowns
    "BETWEEN_FIGHTS_COOLDOWN": 1,            # Y Time between fights
    "DUEL_COOLDOWN": 480,                    # Y Time between duels
    "LEAGUE_DUEL_COOLDOWN": 7200,            # Y 2 hours - league duel task cooldown
    "GUILD_BATTLES_COOLDOWN": 14400,         # Y 4 hours - guild battles task cooldown
    
    # Event timers
    "TREASURE_EVENT_COOLDOWN": 10800,        # Y 3 hours - treasure reveal cooldown
    "TREASURE_EVENT_CHECK_RETRY": 60,        # Y Retry after 60 seconds if on cooldown
    
    # Inventory timers
    "SELL_INVENTORY_COOLDOWN": 1800,         # Y 30 minutes
    "BOOSTER_BUFFER": 172800,                # Y 48 hours (2 days) - try to buy a booster if the old one is expiring within this time

    "FALLBACK_TIMER": 3600,                  # 1 hour fallback when no action available
    
    # Daily reset timers
    "DAILY_RESET_BUFFER_MINUTES": 5,         # Minutes after midnight for daily reset
    "DAILY_RESET_HOUR": 0,                   # Hour of daily reset (0 = midnight)
    "DAILY_RESET_MINUTE": 0,                 # Minute of daily reset
}