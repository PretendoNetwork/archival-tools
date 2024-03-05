import os
import sys
import anyio
import requests
from dotenv import load_dotenv
from nintendo.nex import backend, ranking, datastore, settings, prudp, authentication, rmc
from nintendo.nex.common import RMCError
from nintendo import nnas
from anynet import udp, tls, websocket, util, \
	scheduler, crypto, streams, http
import hashlib
import hmac
import struct
import threading
import time
import sqlite3
from multiprocessing import Process, Lock, Queue, Array
import json
import queue

import logging
logging.basicConfig(level=logging.FATAL)

load_dotenv()

DEVICE_ID = int(os.getenv('DEVICE_ID'))
SERIAL_NUMBER = os.getenv('SERIAL_NUMBER')
SYSTEM_VERSION = int(os.getenv('SYSTEM_VERSION'), 16)
REGION_ID = int(os.getenv('REGION_ID'))
COUNTRY_NAME = os.getenv('COUNTRY')
LANGUAGE = os.getenv('LANGUAGE')

USERNAME = os.getenv('NEX_USERNAME')
PASSWORD = os.getenv('NEX_PASSWORD')

ORDINAL_RANKING = 1 # 1234 rather than 1224

# Category testing thread
def range_test_category(access_key, nex_version, host, port, pid, password, start, end, found_queue, num_tested_queue):
	async def run():
		s = settings.default()
		s.configure(access_key, nex_version)

		try:
			async with backend.connect(s, host, port) as be:
				async with be.login(pid, password) as client:
					ranking_client = ranking.RankingClient(client)

					num_tested = 0
					for category in range(start, end):
						try:
							order_param = ranking.RankingOrderParam()
							order_param.offset = 0
							order_param.count = 1

							_ = await ranking_client.get_ranking(
								ranking.RankingMode.GLOBAL, #Get the global leaderboard
								category, #Category, this is 3-A (Magrove Cove)
								order_param,
								0, 0
							)

							# No exception, this is a valid category
							found_queue.put(category)
						except Exception:
							None

						num_tested += 1

						if num_tested % 100 == 0:
							num_tested_queue.put(100)
		except Exception as e:
			print(e)

		found_queue.put(-1)
	anyio.run(run)

def print_categories(num_processes, found_queue, num_tested_queue):
	begin = time.perf_counter()
	num_tested = 0
	num_sentinels = 0
	while True:
		time.sleep(0.1)

		try:
			category = found_queue.get(block=False)

			# Use sentinels
			if category == -1:
				num_sentinels += 1
				if num_sentinels == num_processes:
					print("Ending print process")
					break

			print("Found category %d" % category)
		except queue.Empty:
			None

		try:
			num_tested_add = num_tested_queue.get(block=False)
			num_tested += num_tested_add

			cur = time.perf_counter()
			print('Tested %d in %f seconds, would take %d seconds or %d days' % (num_tested, cur - begin, (cur - begin) / num_tested * pow(2, 32), ((cur - begin) / num_tested * pow(2, 32)) / 86400))
		except queue.Empty:
			None

async def main():
	con = sqlite3.connect("ranking.db")
	cur = con.cursor()
	cur.execute("""
CREATE TABLE IF NOT EXISTS ranking (
	game TEXT NOT NULL,
	id TEXT NOT NULL,
	pid TEXT NOT NULL,
	rank INTEGER NOT NULL,
	category INTEGER NOT NULL,
	score INTEGER NOT NULL,
	param TEXT NOT NULL,
	data BLOB,
	update_time INTEGER
)""")
	cur.execute("""
CREATE TABLE IF NOT EXISTS ranking_group (
	game TEXT NOT NULL,
	id TEXT NOT NULL,
	pid TEXT NOT NULL,
	rank INTEGER NOT NULL,
	ranking_group INTEGER NOT NULL,
	ranking_index INTEGER NOT NULL
)""")
	cur.execute("""
CREATE TABLE IF NOT EXISTS ranking_param_data (
	game TEXT NOT NULL,
	id TEXT NOT NULL,
	pid TEXT NOT NULL,
	rank INTEGER NOT NULL,
	data BLOB
)""")
	
	f = open('../find-nex-servers/nexwiiu.json')
	nex_wiiu_games = json.load(f)["games"]
	f.close()

	for i, game in enumerate(nex_wiiu_games):
		print("%s (%d out of %d)" % (game["name"].replace('\n', ' '), i, len(nex_wiiu_games)))

		nas = nnas.NNASClient()
		nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
		nas.set_title(game["aid"], game["av"])
		nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)
		
		access_token = await nas.login(USERNAME, PASSWORD)
		
		nex_token = await nas.get_nex_token(access_token.token, game["id"])

		nex_version = game['nex'][0][0] * 10000 + game['nex'][0][1] * 100 + game['nex'][0][2]

		pretty_game_id = hex(game['aid'])[2:].upper()

		"""
		# Run everything in processes
		num_processes = 8
		range_size = int(pow(2, 32) / num_processes)

		found_queue = Queue()
		num_tested_queue = Queue()

		processes = [Process(target=range_test_category,
			args=(game["key"], nex_version, nex_token.host, nex_token.port, str(nex_token.pid), nex_token.password, i * range_size, i * range_size + 1000, found_queue, num_tested_queue)) for i in range(num_processes)]
		# Queue for printing number tested and found categories
		processes.append(Process(target=print_categories, args=(num_processes, found_queue, num_tested_queue)))
		for p in processes:
			p.start()
		for p in processes:
			p.join()

		continue
		"""
		
		s = settings.default()
		s.configure(game["key"], nex_version)
		async with backend.connect(s, nex_token.host, nex_token.port) as be:
			async with be.login(str(nex_token.pid), nex_token.password) as client:
				ranking_client = ranking.RankingClient(client)
				store = datastore.DataStoreClient(client)

				valid_categories = []
				num_tested = 0

				for category in range(1000):
					try:
						order_param = ranking.RankingOrderParam()
						order_param.offset = 0
						order_param.count = 1

						_ = await ranking_client.get_ranking(
							ranking.RankingMode.GLOBAL, #Get the global leaderboard
							category, #Category, this is 3-A (Magrove Cove)
							order_param,
							0, 0
						)

						# No exception, this is a valid category
						valid_categories.append(category)
						print("Found category %d" % category)
					except Exception:
						None

					num_tested += 1

					if num_tested % 10 == 0:
						print("Tested %d categories" % num_tested)

				for category in valid_categories:
					last_rank_seen = 0
					num_ranks_seen = 0
					last_pid_seen = None

					# Try offset
					cur_offset = 0
					offset_interval = 255
					finish_after_this_one = False
					while True:
						try:
							order_param = ranking.RankingOrderParam()
							order_param.order_calc = ORDINAL_RANKING
							order_param.offset = cur_offset
							order_param.count = offset_interval

							rankings = await ranking_client.get_ranking(
								ranking.RankingMode.GLOBAL, # Get the global leaderboard
								category,
								order_param,
								0, 0
							)

							con.executemany("INSERT INTO ranking (game, id, pid, rank, category, score, param, data, update_time) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
								[(pretty_game_id, str(entry.unique_id), str(entry.pid), entry.rank, entry.category, entry.score, str(entry.param), entry.common_data, entry.update_time) for entry in rankings.data])
							con.executemany("INSERT INTO ranking_group (game, id, pid, rank, ranking_group, ranking_index) values (?, ?, ?, ?, ?, ?)",
								[(pretty_game_id, str(entry.unique_id), str(entry.pid), entry.rank, group, i) for entry in rankings.data for i, group in enumerate(entry.groups)])
							con.commit()

							for entry in rankings.data:
								if entry.param:
									get_param = datastore.DataStorePrepareGetParam()
									get_param.data_id = entry.param

									req_info = await store.prepare_get_object(get_param)
									headers = {header.key: header.value for header in req_info.headers}
									response = await http.get(req_info.url, headers=headers)

									if response.success():
										con.executemany("INSERT INTO ranking_param_data (game, id, pid, rank, data) values (?, ?, ?, ?, ?)",
											[(pretty_game_id, str(entry.unique_id), str(entry.pid), entry.rank, response.body)])
									else:
										print("Could not download param for %d" % entry.rank)

							last_rank_seen = rankings.data[-1].rank
							last_pid_seen = rankings.data[-1].pid
							num_ranks_seen += len(rankings.data)

							print("Have %d out of %d for %s (%d out of %d)" % (num_ranks_seen, rankings.total, game["name"].replace('\n', ' '), i, len(nex_wiiu_games)))

							if finish_after_this_one:
								break

							cur_offset += len(rankings.data)
						except RMCError:
							# This codepath does not appear to exist
							break
							"""
							# Decrease offset_interval by 1 and try again
							finish_after_this_one = True
							offset_interval -= 1

							print("Decreasing interval to %d" % offset_interval)

							if offset_interval == 0:
								break
							"""

					# For games that limit to 1000 try mode = 1 approach (around specific player)
					while True:
						try:
							order_param = ranking.RankingOrderParam()
							order_param.order_calc = ORDINAL_RANKING
							order_param.offset = 0
							order_param.count = offset_interval

							rankings = await ranking_client.get_ranking(
								ranking.RankingMode.GLOBAL_AROUND_SELF, # Get the leaderboard around this player
								category,
								order_param,
								0, last_pid_seen
							)

							rankings.data = list(filter(lambda entry: entry.rank > last_rank_seen, rankings.data))

							# If none of the players around this player are unique assume done for now
							if len(rankings.data) == 0:
								break

							# Have to subtract offset_interval from ranking for some reason (likely because this player is rank 255 or something)
							con.executemany("INSERT INTO ranking (game, id, pid, rank, category, score, param, data, update_time) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
								[(pretty_game_id, str(entry.unique_id), str(entry.pid), entry.rank, entry.category, entry.score, str(entry.param), entry.common_data, entry.update_time) for entry in rankings.data])
							con.executemany("INSERT INTO ranking_group (game, id, pid, rank, ranking_group, ranking_index) values (?, ?, ?, ?, ?, ?)",
								[(pretty_game_id, str(entry.unique_id), str(entry.pid), entry.rank, group, i) for entry in rankings.data for i, group in enumerate(entry.groups)])
							con.commit()

							for entry in rankings.data:
								if entry.param:
									get_param = datastore.DataStorePrepareGetParam()
									get_param.data_id = entry.param

									req_info = await store.prepare_get_object(get_param)
									headers = {header.key: header.value for header in req_info.headers}
									response = await http.get(req_info.url, headers=headers)

									if response.success():
										con.executemany("INSERT INTO ranking_param_data (game, id, pid, rank, data) values (?, ?, ?, ?, ?)",
											[(pretty_game_id, str(entry.unique_id), str(entry.pid), entry.rank, response.body)])
									else:
										print("Could not download param for %d" % entry.rank)

							last_rank_seen = rankings.data[-1].rank
							last_pid_seen = rankings.data[-1].pid
							num_ranks_seen += len(rankings.data)

							print("Have %d out of %d for %s (%d out of %d)" % (num_ranks_seen, rankings.total, game["name"].replace('\n', ' '), i, len(nex_wiiu_games)))
						except RMCError:
							break

if __name__ == '__main__':
	anyio.run(main)