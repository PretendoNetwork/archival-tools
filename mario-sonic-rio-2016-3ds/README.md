# Mario & Sonic Rio 2016 (3DS)
## Download all leaderboard data for all available events

# Usage
Create `.env` from `example.env` and fill in your 3DS NEX details. To get your username and password, use this homebrew https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password

Run `python3 archive.py`

# Meta Data
This script will store the leaderboard data in the `data` directory. Each folder inside `data` is the leaderboards event ID

Each event folder contains a `rankings.json.gz` file. Due to the large size of this data, the data is compressed with gzip at level 9. When decompressed, each file is a JSON array of ranking objects.

The data is stored exactly as the server:

- `category` - The ranking categroy (event ID in this case)
- `common_data` - Metadata about the user *at the time of upload*. Unknown use. Seems to contain Mii data?
- `groups` - Ranking groups. Unknown use. Other M&S games use this for character and country IDs
- `param` - Flags used when uploading the score. Unknown use
- `pid` - NEX PID of the user who owns the ranking
- `rank` - Global leaderboard ranking
- `score` - The actual ranking value. How this is used is context specific
- `unique_id` - Unknown use. Usually 0
- `update_time` - Date the score was uploaded. This is the only field not stored exactly as the server sends it. Converted from the timestamp to a readable date

Example:

```json
{
	"category": 0,
	"common_data": "UgBlAG0AeQAAAAAAAAAAAAAAAAAAAEAARwAqAQMAADBBP9/LsE9jgJn/R9iYQVyHQgoAAG5BUgBlAG0AeQAAAAAAAAAAAAAAAABAQCQAMwcfJcMW7jLFEI0OD2YPAAApAFJIUHIAZQBtAHkAAAAAAAAAAAAAAAAAAABh8w==",
	"groups": [
		0,
		0
	],
	"param": 0,
	"pid": 1876712771,
	"rank": 1,
	"score": 82511,
	"unique_id": 0,
	"update_time": "2022-08-07T12:57:40+00:00"
}
```