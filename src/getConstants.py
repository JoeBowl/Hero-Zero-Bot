"""
This script extracts the values of the constants used in main.py.
The constants are stored in a file called `constants_json.data`, 
which is provided by a network request made by the game Hero Zero:

https://hz-static-2.akamaized.net/assets/data/constants_json.data?(...)

- The `(...)` part is a cache-busting query string with a timestamp or hash.
- This request is made when the game loads in the browser (startup or entering the game).

The file is zlib-compressed JSON and contains all in-game constants needed for:
- Quest energy refill costs
- In-game currency scaling
- Other game values

This script decompresses the file, parses it, and prints the relevant constants for use in calculations.
"""

import zlib
import json

# Read compressed file
with open("src/constants_json.data", "rb") as f:
    compressed_data = f.read()

# Decompress (try standard zlib first)
try:
    decompressed = zlib.decompress(compressed_data)
except zlib.error:
    # Sometimes games use raw deflate
    decompressed = zlib.decompress(compressed_data, -zlib.MAX_WBITS)

# Convert to string
text = decompressed.decode("utf-8")

# Parse JSON
data = json.loads(text)

# Save ALL data to file
with open("src/constants.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

print("Saved full JSON to constants.json")

# Print relevant values
keys = [
    "quest_energy_refill_amount",
    "quest_energy_refill1_cost_factor",
    "quest_energy_refill2_cost_factor",
    "quest_energy_refill3_cost_factor",
    "quest_energy_refill4_cost_factor",
    "quest_energy_refill5_cost_factor",
    "quest_energy_refill6_cost_factor",
    "quest_energy_refill7_cost_factor",
    "quest_energy_refill8_cost_factor",
    "coins_per_time_base",
    "coins_per_time_scale",
    "coins_per_time_level_scale",
    "coins_per_time_level_exp"
]

for k in keys:
    print(f"{k}: {data.get(k)}")