'''
Pretendo Network 2023

This will download rankings from M&S Rio 2016 (WiiU) using NEX to automate the process

Use at your own risk, we are not resposible for any bans

Requires Python 3 and https://github.com/Kinnay/NintendoClients
'''

from nintendo.nex import backend, ranking, settings
from nintendo import nnas
import anyio
import os
import json
import gzip
import base64
import logging
import struct

logging.basicConfig(level=logging.ERROR)

json_file = open('config.json')
config = json.load(json_file)

# * Unique device info
DEVICE_ID = config["DEVICE_ID"]
SERIAL_NUMBER = config["SERIAL_NUMBER"]
SYSTEM_VERSION = config["SYSTEM_VERSION"]
REGION_ID = config["REGION_ID"]
COUNTRY_NAME = config["COUNTRY_NAME"]
LANGUAGE = config["LANGUAGE"]

USERNAME = config["USERNAME"] # * Nintendo Network ID username
PASSWORD = config["PASSWORD"] # * Nintendo Network ID password

'''
Globals, set later
'''
nex_token = None
ranking_client = None

TITLE_ID_US = 0x00050000101E5300
TITLE_VERSION_US = 0x10
GAME_SERVER_ID = 0x10190300
NEX_VERSION = 30901 # * 3.9.1
ACCESS_KEY = "63fecb0f"

'''
NintendoClients does not implement this properly
'''
def new_RankingRankData_load(self, stream, version):
	self.pid = stream.pid()
	self.unique_id = stream.u64()
	self.rank = stream.u32()
	self.category = stream.u32()
	self.score = stream.u32()
	self.groups = stream.list(stream.u8)
	self.param = stream.u64()
	self.common_data = stream.buffer()
	if version >= 1:
		self.update_time = stream.datetime()

'''
Gets rid of the "unexpected version" warning
'''
def new_RankingRankData_max_version(self, settings):
	return 1

ranking.RankingRankData.load = new_RankingRankData_load
ranking.RankingRankData.max_version = new_RankingRankData_max_version

async def main():
	os.makedirs("./data", exist_ok=True)

	await nas_login() # * login with NNID
	await backend_setup() # * setup the backend NEX client and start scraping

async def nas_login():
	global nex_token

	nas = nnas.NNASClient()
	nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
	nas.set_title(TITLE_ID_US, TITLE_VERSION_US)
	nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)

	access_token = await nas.login(USERNAME, PASSWORD)
	nex_token = await nas.get_nex_token(access_token.token, GAME_SERVER_ID)

async def backend_setup():
	global ranking_client

	s = settings.default()
	s.configure(ACCESS_KEY, NEX_VERSION)

	async with backend.connect(s, nex_token.host, nex_token.port) as be:
		async with be.login(str(nex_token.pid), nex_token.password) as client:
			ranking_client = ranking.RankingClient(client)

			await scrape() # * start ripping courses

async def scrape():
	events = {
		0x01: "BMX",
		0x02: "Unknown",
		0x03: "Unknown",
		0x04: "Unknown",
		0x05: "100m",
		0x06: "Rhythmic Gynmastics",
		0x07: "Boxing",
		0x08: "Unknown",
		0x09: "4 x 100m Relay",
		0x0A: "Javelin Throw",
		0x0B: "Triple Jump",
		0x0C: "Swimming",
		0x0D: "Equestrian",
		0x0E: "Archery",
		0x0F: "Unknown",
		0x10: "Unknown",
		0x11: "Unknown",
	}

	characters = {
		0x00: "Mario",
		0x01: "Unknown",
		0x02: "Peach",
		0x03: "Daisy",
		0x04: "Bowser",
		0x05: "Unknown",
		0x06: "Unknown",
		0x07: "Yoshi",
		0x08: "DK",
		0x09: "Bowser Jr.",
		0x0A: "Sonic",
		0x0B: "Tails",
		0x0C: "Knuckles",
		0x0D: "Amy",
		0x0E: "Unknown",
		0x0F: "Shadow",
		0x10: "Silver",
		0x11: "Unknown",
		0x12: "Blaze",
		0x13: "Vector",
		0x14: "Mii",
		0x15: "Unknown",
		0x17: "Rosalina",
		0x18: "Unknown",
		0x1A: "Unknown",
		0x1B: "Unknown",
		0x1C: "Unknown",
		0x1D: "Wave",
		0x1F: "Unknown",
		0x20: "Unknown",
		0x22: "Unknown",
	}

	countries = {
		0x01: "Algeria", # * This is a guess based on the flag order in Sochi 2014
		0x02: "Angola", # * This is a guess based on the flag order in Sochi 2014
		0x03: "Ivory Coast", # * This is a guess based on the flag order in Sochi 2014
		0x04: "Egypt", # * This is a guess based on the flag order in Sochi 2014
		0x05: "Ethiopia", # * This is a guess based on the flag order in Sochi 2014
		0x06: "Gambia", # * This is a guess based on the flag order in Sochi 2014
		0x07: "Ghana", # * This is a guess based on the flag order in Sochi 2014
		0x08: "Guinea", # * This is a guess based on the flag order in Sochi 2014
		0x09: "Kenya", # * This is a guess based on the flag order in Sochi 2014
		0x0A: "Morocco",
		0x0B: "Nigeria",
		0x0C: "South Africa", # * This is a guess based on the flag order in Sochi 2014
		0x0D: "Senegal", # * This is a guess based on the flag order in Sochi 2014
		0x0E: "Togo", # * This is a guess based on the flag order in Sochi 2014
		0x0F: "Tunisia", # * This is a guess based on the flag order in Sochi 2014
		0x10: "Argentina", # * This is a guess based on the flag order in Sochi 2014
		0x11: "Bahamas", # * This is a guess based on the flag order in Sochi 2014
		0x12: "Bolivia", # * This is a guess based on the flag order in Sochi 2014
		0x13: "Brazil",
		0x14: "Canada", # * This is a guess based on the flag order in Sochi 2014
		0x15: "Chile",
		0x16: "Colombia",
		0x17: "Costa Rica", # * This is a guess based on the flag order in Sochi 2014
		0x18: "Cuba", # * This is a guess based on the flag order in Sochi 2014
		0x19: "Ecuador", # * This is a guess based on the flag order in Sochi 2014
		0x1A: "Honduras", # * This is a guess based on the flag order in Sochi 2014
		0x1B: "Jamaica", # * This is a guess based on the flag order in Sochi 2014
		0x1C: "Mexico",
		0x1D: "Paraguay", # * This is a guess based on the flag order in Sochi 2014
		0x1E: "Peru", # * This is a guess based on the flag order in Sochi 2014
		0x1F: "Trinidad", # * This is a guess based on the flag order in Sochi 2014
		0x20: "Uruguay", # * This is a guess based on the flag order in Sochi 2014
		0x21: "USA",
		0x22: "China", # * This is a guess based on the flag order in Sochi 2014
		0x23: "Hong Kong", # * This is a guess based on the flag order in Sochi 2014
		0x24: "Indonesia", # * This is a guess based on the flag order in Sochi 2014
		0x25: "India", # * This is a guess based on the flag order in Sochi 2014
		0x26: "Iran", # * This is a guess based on the flag order in Sochi 2014
		0x27: "Japan",
		0x28: "Korea", # * This is a guess based on the flag order in Sochi 2014
		0x29: "Saudi Arabia", # * This is a guess based on the flag order in Sochi 2014
		0x2A: "Malaysia", # * This is a guess based on the flag order in Sochi 2014
		0x2B: "Pakistan", # * This is a guess based on the flag order in Sochi 2014
		0x2C: "Philippines", # * This is a guess based on the flag order in Sochi 2014
		0x2D: "Singapore", # * This is a guess based on the flag order in Sochi 2014
		0x2E: "Thailand", # * This is a guess based on the flag order in Sochi 2014
		0x2F: "United Arab Emirates",
		0x30: "Uzbekistan", # * This is a guess based on the flag order in Sochi 2014
		0x31: "Austria", # * This is a guess based on the flag order in Sochi 2014
		0x32: "Belgium", # * This is a guess based on the flag order in Sochi 2014
		0x33: "Bulgaria", # * This is a guess based on the flag order in Sochi 2014
		0x34: "Croatia", # * This is a guess based on the flag order in Sochi 2014
		0x35: "Czechia", # * This is a guess based on the flag order in Sochi 2014
		0x36: "Denmark", # * This is a guess based on the flag order in Sochi 2014
		0x37: "Spain", # * This is a guess based on the flag order in Sochi 2014
		0x38: "Finland", # * This is a guess based on the flag order in Sochi 2014
		0x39: "France",
		0x3A: "Great Britain",
		0x3B: "Germany",
		0x3C: "Greece",
		0x3D: "Hungary", # * This is a guess based on the flag order in Sochi 2014
		0x3E: "Ireland", # * This is a guess based on the flag order in Sochi 2014
		0x3F: "Israel", # * This is a guess based on the flag order in Sochi 2014
		0x40: "Italy",
		0x41: "Netherlands",
		0x42: "Norway", # * This is a guess based on the flag order in Sochi 2014
		0x43: "Poland", # * This is a guess based on the flag order in Sochi 2014
		0x44: "Portugal", # * This is a guess based on the flag order in Sochi 2014
		0x45: "Romania", # * This is a guess based on the flag order in Sochi 2014
		0x46: "Russia", # * This is a guess based on the flag order in Sochi 2014
		0x47: "Slovenia", # * This is a guess based on the flag order in Sochi 2014
		0x48: "Switzerland", # * This is a guess based on the flag order in Sochi 2014
		0x49: "Slovakia", # * This is a guess based on the flag order in Sochi 2014
		0x4A: "Sweden", # * This is a guess based on the flag order in Sochi 2014
		0x4B: "Turkey", # * This is a guess based on the flag order in Sochi 2014
		0x4C: "Ukraine", # * This is a guess based on the flag order in Sochi 2014
		0x4D: "Australia",
		0x4E: "Fiji", # * This is a guess based on the flag order in Sochi 2014
		0x4F: "New Zealand", # * This is a guess based on the flag order in Sochi 2014
	}

	'''
	Subset of events. Not all events
	have a leaderboard
	'''
	categories = [
		0x06, # * Rhythmic Gynmastics
		0x01, # * BMX
		0x0D, # * Equestrian
		0x05, # * 100m
		0x0E, # * Archery
		0x0B, # * Triple Jump
		0x0C, # * Swimming
		0x0A, # * Javelin Throw
		0x09, # * 4 x 100m Relay
	]

	for category in categories:
		'''
		Make 1 request to get the total number of entries first.
		Using mode 0 to get the latest results
		'''
		mode = 0
		order_param = ranking.RankingOrderParam()
		unique_id = 0
		principal_id = 0

		order_param.offset = 0
		order_param.count = 1

		result = await ranking_client.get_ranking(mode, category, order_param, unique_id, principal_id)

		offset = 0
		total = result.total
		remaining = result.total

		leaderboard = []
		leaderboard_name = events[category].replace(" ", "")
		seen_rankings = []

		principal_id = result.data[0].pid

		while remaining > 0:
			print("{0} on offset {1}. {2}/{3} remaining".format(events[category], offset, remaining, total))

			'''
			Using mode 1 as a hack to get around the 1000 offset limit.
			Mode 1 selects entries around "your" entry, but the server
			does not verify if the currently logged in user is the same
			as the user being used in this mode. Thus we can pretend to
			be the last user and continue past the offset limit
			'''
			mode = 1
			order_param = ranking.RankingOrderParam()
			unique_id = 0

			order_param.offset = 0
			order_param.count = 0xFF # * Max we can do in one go
			order_param.order_calc = 1 # * Ordinal (1234) rankings. Prevents duplicate ranking positions (no ties)

			result = await ranking_client.get_ranking(mode, category, order_param, unique_id, principal_id)
			rankings = result.data

			for user in rankings:
				ranking_entry = {
					"pid": user.pid,
					"unique_id": user.unique_id,
					"rank": user.rank,
					"category": user.category,
					"score": user.score,
					"groups": user.groups,
					"param": user.param,
					"common_data": base64.b64encode(user.common_data).decode("utf-8"),
					"update_time": user.update_time.standard_datetime().isoformat(),
				}

				if ranking_entry in seen_rankings:
					# * Ignore duplicates
					continue

				'''
				The player can change their character and country at will.
				As such, the character and country the player was using at
				the time the ranking was uploaded may be different from
				their favorite character/country. The ranking "groups" is
				used in this game to determine which country/character was
				used at the time the ranking was uploaded
				'''
				[completed_country, completed_character] = user.groups

				common_data = user.common_data

				'''
				common_data offsets
				All numbers are BE
				0x00-0x2F: 0x2D character null-terminated name (not the same as NNID username)
				0x30-0x8F: Mii data
				0x90: Country ID
				0x91: Tournaments Cleared
				0x92: Tournament Gold Medals
				0x93: League events Cleared. 0xFF if disabled
				0x94: League event Gold Medals. Only displayed if league events enabled
				0x95: Special Prizes
				0x96-0x97: Carnival Challenges
				0x98: Favorite Event ID
				0x99: Favorite character ID
				0x9A: Flags
				0x9B: Tips
				0x9C-0x9D: Ghost Match Victories
				0x9E-0xA1: Mii Wear
				0xA2-0xA3: Music Tracks
				0xA4: Stamps
				0xA5: Guests Unlocked
				0xA8-0xAB: Total Coins Earned
				0xAC-0xAF: Total Rings Earned
				'''
				name_block = common_data[0x0:0x30]
				mii_data = common_data[0x30:0x90]
				metadata = common_data[0x90:0xB0] # * Unknown what use the rest of the data after this is
				unknown_common_data = common_data[0xB0:]

				name = name_block.split(b'\x00')[0].decode("utf-8", "replace")

				(
					country,
					tournaments_cleared,
					tournaments_gold_medals,
					leagues_cleared,
					leagues_gold_medals,
					special_prizes,
					carnival_challenges,
					favorite_event,
					favorite_character,
					flags,
					tips,
					ghost_match_victories,
					mii_wear,
					music_tracks,
					stamps,
					guests_unlocked,
					total_coins_earned,
					total_rings_earned
				) = struct.unpack(">BBBBBBHBBBBHIHBBxxII", metadata)

				user_data = {
					"event": category,
					"name": name,
					"pid": user.pid,
					"score": user.score,
					"place": user.rank,
					"update_time": user.update_time.standard_datetime().isoformat(),
					"mii_data": base64.b64encode(mii_data).decode("utf-8"),
					"completed_country": {
						"id": completed_country,
						"name": countries.get(completed_country)
					},
					"completed_character": {
						"id": completed_character,
						"name": characters.get(completed_character, "Unknown")
					},
					"user_country": {
						"id": country,
						"name": countries.get(country)
					},
					"tournaments": {
						"cleared": tournaments_cleared,
						"gold_medals": tournaments_gold_medals,
					},
					"leagues": {
						"cleared": leagues_cleared if leagues_cleared != 0xFF else 0,
						"gold_medals": leagues_gold_medals,
					},
					"favorite_event": {
						"id":  favorite_event,
						"name": events.get(favorite_event, "Unknown")
					},
					"favorite_character": {
						"id":  favorite_character,
						"name": characters.get(favorite_character, "Unknown")
					},
					"total_coins_earned": total_coins_earned,
					"total_rings_earned": total_rings_earned,
					"clear_counts": {
						"special_prizes": special_prizes,
						"ghost_match_victories": ghost_match_victories,
						"carnival_challenges":  carnival_challenges,
						"guests": guests_unlocked
					},
					"collectables": {
						"flags": flags,
						"tips": tips,
						"mii_wear": mii_wear,
						"music_tracks": music_tracks,
						"stamps": stamps
					},
					"unknown_common_data": unknown_common_data.hex(),
					"ranking_raw": ranking_entry
				}

				leaderboard.append(user_data)
				principal_id = user.pid
				offset += 1
				remaining -= 1
				seen_rankings.append(ranking_entry)

		print("Writing ./data/{0}/rankings.json.gz".format(category))
		leaderboard_data = json.dumps(leaderboard)
		os.makedirs("./data/{0}".format(category), exist_ok=True)
		await write_to_file("./data/{0}/rankings.json.gz".format(category), leaderboard_data.encode("utf-8"))

async def write_to_file(path, data):
	with gzip.open(path, "w", compresslevel=9) as f:       # * 4. fewer bytes (i.e. gzip)
		f.write(data)

anyio.run(main)
