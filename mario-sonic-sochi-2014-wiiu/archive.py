'''
Pretendo Network 2023

This will download rankings and "best runs" from M&S Sochi 2014 (WiiU) using NEX to automate the process

Use at your own risk, we are not resposible for any bans

Requires Python 3 and https://github.com/Kinnay/NintendoClients
'''

from nintendo.nex import backend, ranking, datastore, settings
from nintendo import nnas
from anynet import http
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

# Unique device info
DEVICE_ID = config["DEVICE_ID"]
SERIAL_NUMBER = config["SERIAL_NUMBER"]
SYSTEM_VERSION = config["SYSTEM_VERSION"]
REGION_ID = config["REGION_ID"]
COUNTRY_NAME = config["COUNTRY_NAME"]
LANGUAGE = config["LANGUAGE"]

USERNAME = config["USERNAME"] # Nintendo Network ID username
PASSWORD = config["PASSWORD"] # Nintendo Network ID password

'''
Globals, set later
'''
nex_token = None
ranking_client = None
datastore_client = None

TITLE_ID_US = 0x0005000010106900
TITLE_VERSION_US = 0x20
GAME_SERVER_ID = 0x10106900
NEX_VERSION = 30413 # 3.4.13
ACCESS_KEY = "585214a5"

async def main():
	os.makedirs("./data", exist_ok=True)
	os.makedirs("./data/rankings", exist_ok=True) # Stores ranking data
	os.makedirs("./data/objects", exist_ok=True) # Stores "best run" DataStore objects
	os.makedirs("./data/meta_binaries", exist_ok=True) # Stores the meta binary for DataStore objects

	await nas_login() # login with NNID
	await backend_setup() # setup the backend NEX client and start scraping

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
	global datastore_client

	s = settings.default()
	s.configure(ACCESS_KEY, NEX_VERSION)

	async with backend.connect(s, nex_token.host, nex_token.port) as be:
		async with be.login(str(nex_token.pid), nex_token.password) as client:
			ranking_client = ranking.RankingClient(client)
			datastore_client = datastore.DataStoreClient(client)

			await scrape() # start ripping courses

async def scrape():
	events = {
		0x0A: "Alpine Skiing Downhill",
		0x0B: "Ski Jumping Large Hill",
		0x0C: "Freestyle Ski Cross",
		0x0D: "Biathlon",
		0x0E: "Snowboard Parallel Giant Slalom",
		0x0F: "Snowboard Cross",
		0x10: "Speed Skating 500m",
		0x11: "Short Track Speed Skating 1000m",
		0x12: "Skeleton",
		0x13: "4-man Bobsleigh",
		0x14: "Winter Sports Champion Race",
		0x15: "Groove Pipe Snowboard",
		0x16: "Roller Coaster Bobsleigh",
		0x17: "Bullet Bill Sledge Race",
	}

	characters = {
		0x04: "Daisy",
		0x08: "Yoshi",
		0x09: "Donkey Kong",
		0x0A: "Bowser Jr.",
		0x0B: "Sonic",
		0x10: "Shadow",
		0x12: "Metal Sonic",
		0x14: "Vector",
		0x15: "Mii",
	}

	countries = {
		0x01: "Algeria", # This is a guess based on the flag order in Sochi 2014
		0x02: "Angola", # This is a guess based on the flag order in Sochi 2014
		0x03: "Ivory Coast", # This is a guess based on the flag order in Sochi 2014
		0x04: "Egypt", # This is a guess based on the flag order in Sochi 2014
		0x05: "Ethiopia", # This is a guess based on the flag order in Sochi 2014
		0x06: "Gambia", # This is a guess based on the flag order in Sochi 2014
		0x07: "Ghana", # This is a guess based on the flag order in Sochi 2014
		0x08: "Guinea", # This is a guess based on the flag order in Sochi 2014
		0x09: "Kenya", # This is a guess based on the flag order in Sochi 2014
		0x0A: "Morocco",
		0x0B: "Nigeria",
		0x0C: "South Africa", # This is a guess based on the flag order in Sochi 2014
		0x0D: "Senegal", # This is a guess based on the flag order in Sochi 2014
		0x0E: "Togo", # This is a guess based on the flag order in Sochi 2014
		0x0F: "Tunisia", # This is a guess based on the flag order in Sochi 2014
		0x10: "Argentina", # This is a guess based on the flag order in Sochi 2014
		0x11: "Bahamas", # This is a guess based on the flag order in Sochi 2014
		0x12: "Bolivia", # This is a guess based on the flag order in Sochi 2014
		0x13: "Brazil",
		0x14: "Canada", # This is a guess based on the flag order in Sochi 2014
		0x15: "Chile",
		0x16: "Colombia",
		0x17: "Costa Rica", # This is a guess based on the flag order in Sochi 2014
		0x18: "Cuba", # This is a guess based on the flag order in Sochi 2014
		0x19: "Ecuador", # This is a guess based on the flag order in Sochi 2014
		0x1A: "Honduras", # This is a guess based on the flag order in Sochi 2014
		0x1B: "Jamaica", # This is a guess based on the flag order in Sochi 2014
		0x1C: "Mexico",
		0x1D: "Paraguay", # This is a guess based on the flag order in Sochi 2014
		0x1E: "Peru", # This is a guess based on the flag order in Sochi 2014
		0x1F: "Trinidad", # This is a guess based on the flag order in Sochi 2014
		0x20: "Uruguay", # This is a guess based on the flag order in Sochi 2014
		0x21: "USA",
		0x22: "China", # This is a guess based on the flag order in Sochi 2014
		0x23: "Hong Kong", # This is a guess based on the flag order in Sochi 2014
		0x24: "Indonesia", # This is a guess based on the flag order in Sochi 2014
		0x25: "India", # This is a guess based on the flag order in Sochi 2014
		0x26: "Iran", # This is a guess based on the flag order in Sochi 2014
		0x27: "Japan",
		0x28: "Korea", # This is a guess based on the flag order in Sochi 2014
		0x29: "Saudi Arabia", # This is a guess based on the flag order in Sochi 2014
		0x2A: "Malaysia", # This is a guess based on the flag order in Sochi 2014
		0x2B: "Pakistan", # This is a guess based on the flag order in Sochi 2014
		0x2C: "Philippines", # This is a guess based on the flag order in Sochi 2014
		0x2D: "Singapore", # This is a guess based on the flag order in Sochi 2014
		0x2E: "Thailand", # This is a guess based on the flag order in Sochi 2014
		0x2F: "United Arab Emirates",
		0x30: "Uzbekistan", # This is a guess based on the flag order in Sochi 2014
		0x31: "Austria", # This is a guess based on the flag order in Sochi 2014
		0x32: "Belgium", # This is a guess based on the flag order in Sochi 2014
		0x33: "Bulgaria", # This is a guess based on the flag order in Sochi 2014
		0x34: "Croatia", # This is a guess based on the flag order in Sochi 2014
		0x35: "Czechia", # This is a guess based on the flag order in Sochi 2014
		0x36: "Denmark", # This is a guess based on the flag order in Sochi 2014
		0x37: "Spain", # This is a guess based on the flag order in Sochi 2014
		0x38: "Finland", # This is a guess based on the flag order in Sochi 2014
		0x39: "France",
		0x3A: "Great Britain",
		0x3B: "Germany",
		0x3C: "Greece",
		0x3D: "Hungary", # This is a guess based on the flag order in Sochi 2014
		0x3E: "Ireland", # This is a guess based on the flag order in Sochi 2014
		0x3F: "Israel", # This is a guess based on the flag order in Sochi 2014
		0x40: "Italy",
		0x41: "Netherlands",
		0x42: "Norway", # This is a guess based on the flag order in Sochi 2014
		0x43: "Poland", # This is a guess based on the flag order in Sochi 2014
		0x44: "Portugal", # This is a guess based on the flag order in Sochi 2014
		0x45: "Romania", # This is a guess based on the flag order in Sochi 2014
		0x46: "Russia", # This is a guess based on the flag order in Sochi 2014
		0x47: "Slovenia", # This is a guess based on the flag order in Sochi 2014
		0x48: "Switzerland", # This is a guess based on the flag order in Sochi 2014
		0x49: "Slovakia", # This is a guess based on the flag order in Sochi 2014
		0x4A: "Sweden", # This is a guess based on the flag order in Sochi 2014
		0x4B: "Turkey", # This is a guess based on the flag order in Sochi 2014
		0x4C: "Ukraine", # This is a guess based on the flag order in Sochi 2014
		0x4D: "Australia",
		0x4E: "Fiji", # This is a guess based on the flag order in Sochi 2014
		0x4F: "New Zealand", # This is a guess based on the flag order in Sochi 2014
	}

	categories = [
		0x0A, # Alpine Skiing Downhill
		0x0B, # Ski Jumping Large Hill
		0x0C, # Freestyle Ski Cross
		0x0D, # Biathlon
		0x0E, # Snowboard Parallel Giant Slalom
		0x0F, # Snowboard Cross
		0x10, # Speed Skating 500m
		0x11, # Short Track Speed Skating 1000m
		0x12, # Skeleton
		0x13, # 4-man Bobsleigh
		0x14, # Winter Sports Champion Race
		0x15, # Groove Pipe Snowboard
		0x16, # Roller Coaster Bobsleigh
		0x17, # Bullet Bill Sledge Race
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
			order_param.count = 0xFF # Max we can do in one go
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
					"common_data": base64.b64encode(user.common_data).decode("utf-8")
				}

				if ranking_entry in seen_rankings:
					# * Ignore duplicates
					continue

				[completed_country, completed_character] = user.groups

				common_data = user.common_data

				name_block = common_data[0x0:0x18]
				bpfc = common_data[0x18:] # Contains a header, Mii data, and a footer?
				mii_data = bpfc[0x18:0x78] # For easier access

				name = name_block.split(b'\x00\x00')[0].decode("utf-16be", "replace")

				param = datastore.DataStoreGetMetaParam()
				param.persistence_target.owner_id = user.pid
				param.persistence_target.persistence_id = 14
				param.result_option = 4

				result = await datastore_client.get_meta(param)

				if len(result.meta_binary) != 0:
					await write_to_file("./data/meta_binaries/{0}.bin.gz".format(result.data_id), result.meta_binary)

				user_data = {
					"event": category,
					"name": name,
					"pid": user.pid,
					"score": user.score,
					"place": user.rank,
					"mii_data": base64.b64encode(mii_data).decode("utf-8"),
					"meta_binary": {
						"id": result.data_id,
						"created": result.create_time.standard_datetime().isoformat(),
						"updated": result.update_time.standard_datetime().isoformat(),
					},
					"completed_country": {
						"id": completed_country,
						"name": countries.get(completed_country)
					},
					"completed_character": {
						"id": completed_character,
						"name": characters.get(completed_character, "Unknown")
					},
					"bpfc_data": base64.b64encode(mii_data).decode("utf-8"),
					"best_run": {
						"id": user.param,
						"created": "",
						"updated": "",
					},
					"ranking_raw": ranking_entry
				}

				'''
				Entry has a "best run" object in DataStore
				'''
				if user.param != 0:
					param = datastore.DataStoreGetMetaParam()
					param.data_id = user.param

					result = await datastore_client.get_meta(param)

					user_data["best_run"]["created"] = result.create_time.standard_datetime().isoformat();
					user_data["best_run"]["updated"] = result.update_time.standard_datetime().isoformat();

					if len(result.meta_binary) != 0:
						await write_to_file("./data/meta_binaries/{0}.bin.gz".format(result.data_id), result.meta_binary)

					param = datastore.DataStorePrepareGetParam()
					param.data_id = user.param

					result = await datastore_client.prepare_get_object(param)

					headers = {header.key: header.value for header in result.headers}
					url = result.url

					response = await http.get(url, headers=headers)

					await write_to_file("./data/objects/{0}.bin.gz".format(user.param), response.body)

				leaderboard.append(user_data)
				principal_id = user.pid
				offset += 1
				remaining -= 1
				seen_rankings.append(ranking_entry)

		print("Writing ./data/rankings/{0}.json.gz".format(category))
		leaderboard_data = json.dumps(leaderboard)
		await write_to_file("./data/rankings/{0}.json.gz".format(category), leaderboard_data.encode("utf-8"))

async def write_to_file(path, data):
	with gzip.open(path, "w", compresslevel=9) as f:
		f.write(data)

anyio.run(main)
