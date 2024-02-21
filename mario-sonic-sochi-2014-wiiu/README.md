# Mario & Sonic Sochi 2014
## Download all leaderboard data for all available events

## THIS IS VERY SLOW. IT MAKES SEVERAL NEX REQUESTS AND DOWNLOADS FILES FROM AN S3 SERVER
## GETTING A FULL DUMP OF ALL DATA WILL TAKE SEVERAL DAYS, OR EVEN WEEKS, RUNNING NONSTOP

# Usage
Create `config.json` from `example.config.json` and fill in your console and NNID details
Run `python3 archive.py`

# Meta Data
This script will store the leaderboard and user data in the `data` directory. The `data` folder contains the following folders

- `data/meta_binaries` - MetaBinary blobs for objects in DataStore. File name is the DataStore DataID. Usually a users user data
- `data/objects` - Object blobs for objects in DataStore. File name is the DataStore DataID. Usually a users best run for an event
- `data/rankings` - Contains JSON files of all the rankings for a given event. File name is the event ID

All data is compressed with gzip at level 9. When decompressed, each file in `data/rankings` is a JSON array of ranking objects

The format of a ranking object is as follows:

- `event` - The event ID the record is for (same as the parent folder)
- `name` - The users name in game
- `pid` - The users NNID PID
- `score` - The score for the ranking. Different events format this value differently
- `place` - The records global ranking (`1` = 1st, `2` = 2nd, etc)
- `mii_data` - The users NNID Mii data. Extracted from the `BPFC` data
- `meta_binary.id` - DataStore DataID for the users meta binary. Contains unknown data
- `meta_binary.created` - Time the users data was updated in DataStore
- `meta_binary.updated` - Time the users data was updated in DataStore
- `completed_country.id` - The country (flag) ID the user was using at the time of making the entry
- `completed_country.name` - The country (flag) name the user was using at the time of making the entry. "Unknown" if unknown
- `completed_character.id` - The character ID the user was using at the time of making the entry
- `completed_character.name` - The character name the user was using at the time of making the entry. "Unknown" if unknown
- `bpfc_data` - Users `BPFC` data. Contains a small header, followed by normal Mii data and a small footer. Header and footer contain unknown data
- `best_run.id` - DataStore DataID for the users best run. 0 if no best run available. Contains unknown data
- `best_run.created` - Time the users best run was updated in DataStore. Empty string if no best run available
- `best_run.updated` - Time the users best run was updated in DataStore. Empty string if no best run available
- `ranking_raw` - The raw ranking data as sent by the server

Example:

```json
{
	"event": 10,
	"name": "★Harrison☆",
	"pid": 1783814945,
	"score": 84510,
	"place": 1,
	"mii_data": "AwAAQODjGSQAhODQ3F6pumzhV6Qy9AAAYgIFJkgAYQByAHIAaQBzAG8AbgAGJkBAAgAFA6VmYxahNEUUYRQPZA4AACmoWUhQTQBlACAAbABvAGwAAABhAHcAYQAAALsN",
	"meta_binary": {
		"id": 1807365,
		"created": "2015-01-10T15:24:20+00:00",
		"updated": "2023-09-24T17:58:09+00:00"
	},
	"completed_country": {
		"id": 58,
		"name": "Great Britain"
	},
	"completed_character": {
		"id": 18,
		"name": "Metal Sonic"
	},
	"bpfc_data": "AwAAQODjGSQAhODQ3F6pumzhV6Qy9AAAYgIFJkgAYQByAHIAaQBzAG8AbgAGJkBAAgAFA6VmYxahNEUUYRQPZA4AACmoWUhQTQBlACAAbABvAGwAAABhAHcAYQAAALsN",
	"best_run": {
		"id": 2785933,
		"created": "2023-08-05T14:49:23+00:00",
		"updated": "2023-08-05T14:49:23+00:00"
	}
}
```

## Notes

1. Not every character name is known. The ID is stored as well as the name. If the name is not known, `name` will be `Unknown`
2. Nintendo seems to have cases where several records have the same rank position. No filtering is done to prevent this, the data is saved exactly as Nintendo sends it