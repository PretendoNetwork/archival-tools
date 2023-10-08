# Mario & Sonic Rio 2016
## Download all leaderboard data for all available events

# Usage
Create `config.json` from `example.config.json` and fill in your console and NNID details
Run `python3 archive.py`

# Meta Data
This script will store the leaderboard data in the `data` directory. Each folder inside `data` is the leaderboards event ID

- 1 = BMX
- 5 = 100m
- 6 = Rhythmic Gynmastics
- 9 = 4 x 100m Relay
- 10 = Javelin Throw
- 11 = Triple Jump
- 12 = Swimming
- 13 = Equestrian
- 14 = Archery

Each event folder contains a `rankings.json.gz` file. Due to the large size of this data, the data is compressed with gzip at level 9. When decompressed, each file is a JSON array of ranking objects

The format of a ranking object is as follows:

- `event` - The event ID the record is for (same as the parent folder)
- `name` - The users name in game
- `pid` - The users NNID PID
- `score` - The score for the ranking. Different events format this value differently
- `place` - The records global ranking (`1` = 1st, `2` = 2nd, etc)
- `update_time` - The time this record was created/updated
- `mii_data` - The users NNID Mii data
- `completed_country.id` - The country (flag) ID the user was using at the time of making the entry
- `completed_country.name` - The country (flag) name the user was using at the time of making the entry. "Unknown" if unknown
- `completed_character.id` - The character ID the user was using at the time of making the entry
- `completed_character.name` - The character name the user was using at the time of making the entry. "Unknown" if unknown
- `user_country.id` - The country (flag) ID the user typically uses
- `user_country.name` - The country (flag) name the user typically uses. "Unknown" if unknown
- `tournaments.cleared` - The number of tournaments cleared
- `tournaments.gold_medals` - The number of gold medals earned in tournaments
- `leagues.cleared` - The number of leagues cleared
- `leagues.gold_medals` - The number of gold medals earned in leagues
- `favorite_event.id` - The event ID for the users favorite event
- `favorite_event.name` - The event name for the users favorite event. "Unknown" if unknown
- `favorite_character.id` - The character ID for the users favorite character
- `favorite_character.name` - The character name for the users favorite character. "Unknown" if unknown
- `total_coins_earned` - The total number of coins the user has earned
- `total_rings_earned` - The total number of rings the user has earned
- `clear_counts.special_prizes` - Number of special prizes
- `clear_counts.ghost_match_victories` - Number of ghost matches the user has won
- `clear_counts.carnival_challenges` - Number of carnival challenges the user has cleared
- `clear_counts.guests` - Number of guests the user has unlocked
- `collectables.flags` - Number of flags the user has collected
- `collectables.tips` - Number of tips the user has collected
- `collectables.mii_wear` - Number of Mii wear the user has collected
- `collectables.music_tracks` - Number of music tracks the user has collected
- `collectables.stamps` - Number of stamps the user has collected

Example:

```json
{
	"event": 6,
	"name": "UniteKoopa",
	"pid": 1761782268,
	"score": 19855,
	"place": 1,
	"update_time": "2017-10-21T03:34:40+00:00",
	"mii_data": "AwAAQApkmkXgRHBA2QAdZWLzgumdlwAAAFhVAG4AaQB0AGUASwBvAG8AcABhAFI9AgAzByBpRBTvNEUMgRAIZg0AACkAUkhQQwBoAGEAcgBnAGUAAAAAAAAAAAAAAKYn",
	"completed_country": {
		"id": 77,
		"name": "Australia"
	},
	"completed_character": {
		"id": 11,
		"name": "Tails"
	},
	"user_country": {
		"id": 33,
		"name": "USA"
	},
	"tournaments": {
		"cleared": 68,
		"gold_medals": 68
	},
	"leagues": {
		"cleared": 0,
		"gold_medals": 0
	},
	"favorite_event": {
		"id": 6,
		"name": "Rhythmic Gynmastics"
	},
	"favorite_character": {
		"id": 11,
		"name": "Tails"
	},
	"total_coins_earned": 49599,
	"total_rings_earned": 67530,
	"clear_counts": {
		"special_prizes": 68,
		"ghost_match_victories": 335,
		"carnival_challenges": 68,
		"guests": 14
	},
	"collectables": {
		"flags": 113,
		"tips": 91,
		"mii_wear": 402,
		"music_tracks": 57,
		"stamps": 100
	}
}
```

## Notes

1. Not every event name is known. The ID is stored as well as the name. If the name is not known, `name` will be `Unknown`
2. Not every character name is known. The ID is stored as well as the name. If the name is not known, `name` will be `Unknown`
3. Nintendo seems to have cases where several records have the same rank position. No filtering is done to prevent this, the data is saved exactly as Nintendo sends it
4. The character and flag the user was using at the time of making the record can differ from their favorite character and flag. As such it is stored separately