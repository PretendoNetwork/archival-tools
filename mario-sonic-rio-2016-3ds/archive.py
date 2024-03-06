'''
Pretendo Network 2023

This will download rankings from M&S Rio 2016 (WiiU) using NEX to automate the process

Use at your own risk, we are not resposible for any bans

Requires Python 3 and https://github.com/Kinnay/NintendoClients
'''

import os
import json
import gzip
import anyio
import base64
from dotenv import load_dotenv
from nintendo.nex import backend, ranking, settings
from anynet import http

load_dotenv()

# * Dump using https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password
NEX_USERNAME = os.getenv('NEX_3DS_USERNAME')
NEX_PASSWORD = os.getenv('NEX_3DS_PASSWORD')
NEX_VERSION = 30901 # * 3.9.1
ACCESS_KEY = "a2dbfa39"

ranking_client = None

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
	global ranking_client

	os.makedirs("./data", exist_ok=True)

	s = settings.default()
	s.configure(ACCESS_KEY, NEX_VERSION)

	# * Skip NASC
	async with backend.connect(s, "34.208.166.202", "40760") as be:
		async with be.login(NEX_USERNAME, NEX_PASSWORD) as client:
			ranking_client = ranking.RankingClient(client)

			await scrape()

async def scrape():
	# * Ordered as they appear in-game
	categories = [
		0x00,
		0x01,
		0x02,
		0x03,
		0x04,
		0x05,
		0x06,
		0x07,
		0x09,
		0x08,
		0x0B,
		0x0A,
		0x0D,
		0x0C,
		0x0E,
		0x0F,
		0x10,
		0x11,
		0x12,
		0x13,
		0x14,
		0x15,
		0x16,
		0x17,
		0x18
	]

	for category in categories:
		'''
		Make an initial request to get the total number of rankings in the category.
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

		principal_id = result.data[0].pid

		leaderboard = []
		seen_rankings = []

		while remaining > 0:
			print("Category {0} on offset {1}. {2}/{3} remaining".format(category, offset, remaining, total))

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

			for entry in rankings:
				ranking_entry = {
					"pid": entry.pid,
					"unique_id": entry.unique_id,
					"rank": entry.rank,
					"category": entry.category,
					"score": entry.score,
					"groups": entry.groups,
					"param": entry.param,
					"common_data": base64.b64encode(entry.common_data).decode("utf-8"),
					"update_time": entry.update_time.standard_datetime().isoformat(),
				}

				if ranking_entry in seen_rankings:
					# * Ignore duplicates
					continue

				leaderboard.append(ranking_entry)
				principal_id = entry.pid
				offset += 1
				remaining -= 1
				seen_rankings.append(ranking_entry)

		print("Writing ./data/{0}/rankings.json.gz".format(category))
		leaderboard_data = json.dumps(leaderboard)
		os.makedirs("./data/{0}".format(category), exist_ok=True)
		await write_to_file("./data/{0}/rankings.json.gz".format(category), leaderboard_data.encode("utf-8"))

async def write_to_file(path, data):
	with gzip.open(path, "w", compresslevel=9) as f:
		f.write(data)

anyio.run(main)
