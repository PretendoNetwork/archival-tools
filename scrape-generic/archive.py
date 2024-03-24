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
import traceback
import asyncio

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

def run_category_scrape(category, db_lock, log_lock, s, host, port, pid, password, game, pretty_game_id, has_datastore, i, nex_wiiu_games):
	async def main():
		async with backend.connect(s, host, port) as be:
				async with be.login(str(pid), password) as client:
					con = sqlite3.connect("ranking.db")
					ranking_client = ranking.RankingClient(client)
					store = datastore.DataStoreClient(client)

					print("Starting category %d" % category)

					last_rank_seen = 0
					num_ranks_seen = 0
					last_pid_seen = None
					last_id_seen = None

					# One request to get first PID and number of rankings, just in case offset based fails on first request
					try:
						order_param = ranking.RankingOrderParam()
						order_param.offset = 0
						order_param.count = 1

						rankings = await ranking_client.get_ranking(
							ranking.RankingMode.GLOBAL, # Get the global leaderboard
							category,
							order_param,
							0, 0
						)

						last_pid_seen = rankings.data[0].pid
						last_id_seen = rankings.data[0].unique_id
					except Exception as e:
							# Protocol is likely incorrect
							log_lock.acquire()
							log_file = open("log.txt", "a", encoding="utf-8")
							print_and_log("Have %d and issue with %s at category %d: %s" % (num_ranks_seen, game["name"].replace('\n', ' '), category, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
							log_file.close()
							log_lock.release()
							return
					
					# Get number of rankings with this category
					num_ranks_seen = list(con.execute("SELECT COUNT(*) FROM ranking WHERE game = ? AND category = ?", (pretty_game_id, category)))[0][0]

					offset_interval = 255
					if num_ranks_seen >= rankings.total:
						log_file = open("log.txt", "a", encoding="utf-8")
						print_and_log("Stopping category %d, already finished" % category, log_file)
						log_file.close()
					elif num_ranks_seen == 0:
						# Try offset
						cur_offset = 0
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

								await add_rankings(category, db_lock, log_lock, rankings, pretty_game_id, has_datastore, store, con)

								last_rank_seen = rankings.data[-1].rank
								last_pid_seen = rankings.data[-1].pid
								last_id_seen = rankings.data[-1].unique_id
								num_ranks_seen += len(rankings.data)

								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d out of %d for category %d for %s (%d out of %d)" % (num_ranks_seen, rankings.total, category, game["name"].replace('\n', ' '), i, len(nex_wiiu_games)), log_file)
								log_file.close()
								log_lock.release()

								if finish_after_this_one:
									break

								cur_offset += len(rankings.data)
							except RMCError as e:
								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d and RMCError with %s at category %d: %s" % (num_ranks_seen, game["name"].replace('\n', ' '), category, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
								log_file.close()
								log_lock.release()
								break
							except Exception as e:
								# Protocol is likely incorrect
								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d and issue with %s at category %d: %s" % (num_ranks_seen, game["name"].replace('\n', ' '), category, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
								log_file.close()
								log_lock.release()
								break

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
									last_id_seen, last_pid_seen
								)

								rankings.data = list(filter(lambda entry: entry.rank > last_rank_seen, rankings.data))

								# If none of the players around this player are unique assume done for now
								if len(rankings.data) == 0:
									break

								await add_rankings(category, db_lock, log_lock, rankings, pretty_game_id, has_datastore, store, con)

								last_rank_seen = rankings.data[-1].rank
								last_pid_seen = rankings.data[-1].pid
								last_id_seen = rankings.data[-1].unique_id
								num_ranks_seen += len(rankings.data)

								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d out of %d for category %d for %s (%d out of %d)" % (num_ranks_seen, rankings.total, category, game["name"].replace('\n', ' '), i, len(nex_wiiu_games)), log_file)
								log_file.close()
								log_lock.release()
							except RMCError as e:
								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d and RMCError with %s at category %d: %s" % (num_ranks_seen, game["name"].replace('\n', ' '), category, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
								log_file.close()
								log_lock.release()
								break
							except Exception as e:
								# Protocol is likely incorrect
								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d and issue with %s at category %d: %s" % (num_ranks_seen, game["name"].replace('\n', ' '), category, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
								log_file.close()
								log_lock.release()
								break
					elif num_ranks_seen < rankings.total:
						# Get last id and pid seen
						result = list(con.execute("SELECT rank, id, pid FROM ranking WHERE game = ? AND category = ? ORDER BY rank DESC LIMIT 1", (pretty_game_id, category)))[0]
						last_rank_seen = int(result[0])
						last_id_seen = int(result[1])
						last_pid_seen = int(result[2])

						# Only use around_self for this
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
									last_id_seen, last_pid_seen
								)

								rankings.data = list(filter(lambda entry: entry.rank > last_rank_seen, rankings.data))

								# If none of the players around this player are unique assume done for now
								if len(rankings.data) == 0:
									break

								await add_rankings(category, db_lock, log_lock, rankings, pretty_game_id, has_datastore, store, con)

								last_rank_seen = rankings.data[-1].rank
								last_pid_seen = rankings.data[-1].pid
								last_id_seen = rankings.data[-1].unique_id
								num_ranks_seen += len(rankings.data)

								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d out of %d for category %d for %s (%d out of %d)" % (num_ranks_seen, rankings.total, category, game["name"].replace('\n', ' '), i, len(nex_wiiu_games)), log_file)
								log_file.close()
								log_lock.release()
							except RMCError as e:
								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d and RMCError with %s at category %d: %s" % (num_ranks_seen, game["name"].replace('\n', ' '), category, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
								log_file.close()
								log_lock.release()
								break
							except Exception as e:
								# Protocol is likely incorrect
								log_lock.acquire()
								log_file = open("log.txt", "a", encoding="utf-8")
								print_and_log("Have %d and issue with %s at category %d: %s" % (num_ranks_seen, game["name"].replace('\n', ' '), category, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
								log_file.close()
								log_lock.release()
								break

					con.close()

	anyio.run(main)

def print_and_log(text, f):
	print(text)
	f.write("%s\n" % text)
	f.flush()

def timestamp_if_not_null(t):
	if t:
		return t.timestamp()
	else:
		return t

async def add_rankings(category, db_lock, log_lock, rankings, pretty_game_id, has_datastore, store, con):
	db_lock.acquire()
	con.executemany("INSERT INTO ranking (game, id, pid, rank, category, score, param, data, update_time) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
		[(pretty_game_id, str(entry.unique_id), str(entry.pid), entry.rank, entry.category, entry.score, str(entry.param), entry.common_data, timestamp_if_not_null(entry.update_time)) for entry in rankings.data])
	con.executemany("INSERT INTO ranking_group (game, pid, rank, category, ranking_group, ranking_index) values (?, ?, ?, ?, ?, ?)",
		[(pretty_game_id, str(entry.pid), entry.rank, category, group, i) for entry in rankings.data for i, group in enumerate(entry.groups)])
	con.commit()
	db_lock.release()

	if has_datastore:
		for entry in rankings.data:
			if entry.param:
				result = None
				try:
					get_meta_param = datastore.DataStoreGetMetaParam()
					get_meta_param.result_option = 4
					get_meta_param.data_id = entry.param
					get_meta_param.persistence_target.owner_id = entry.pid

					result = await store.get_meta(get_meta_param)
				except RMCError as e:
					# Usually nintendo.nex.common.RMCError: Ranking::NotFound, ignore
					None
				except Exception as e:
					log_lock.acquire()
					log_file = open("log.txt", "a", encoding="utf-8")
					print_and_log("Could not download meta param for %d: %s" % (entry.rank, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
					log_file.close()
					log_lock.release()

				response = None
				if result and result.size > 0:
					try:
						get_param = datastore.DataStorePrepareGetParam()
						get_param.data_id = entry.param
						get_param.persistence_target.owner_id = entry.pid

						req_info = await store.prepare_get_object(get_param)
						headers = {header.key: header.value for header in req_info.headers}
						response = await http.get(req_info.url, headers=headers)
						response.raise_if_error()
					except RMCError as e:
						# Usually nintendo.nex.common.RMCError: Ranking::NotFound, ignore
						None
					except Exception as e:
						log_lock.acquire()
						log_file = open("log.txt", "a", encoding="utf-8")
						print_and_log("Could not download param for %d: %s" % (entry.rank, ''.join(traceback.TracebackException.from_exception(e).format())), log_file)
						log_file.close()
						log_lock.release()

				if result:
					db_lock.acquire()
					# TODO store more!
					con.execute("INSERT INTO ranking_meta (game, pid, rank, category, data_id, size, name, data_type, meta_binary, create_time, update_time) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
						(pretty_game_id, str(entry.pid), entry.rank, category, result.data_id, result.size, result.name, result.data_type, result.meta_binary, timestamp_if_not_null(result.create_time), timestamp_if_not_null(result.update_time)))
					if result.size > 0:
						con.execute("INSERT INTO ranking_param_data (game, pid, rank, category, data) values (?, ?, ?, ?, ?)",
							(pretty_game_id, str(entry.pid), entry.rank, category, response.body))

					con.commit()
					db_lock.release()

# NintendoClients does not implement this properly
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

# Gets rid of the "unexpected version" warning
def new_RankingRankData_max_version(self, settings):
	return 1

ranking.RankingRankData.load = new_RankingRankData_load
ranking.RankingRankData.max_version = new_RankingRankData_max_version

async def main():
	if sys.argv[1] == "create":
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
		pid TEXT NOT NULL,
		rank INTEGER NOT NULL,
		category INTEGER NOT NULL,
		ranking_group INTEGER NOT NULL,
		ranking_index INTEGER NOT NULL
	)""")
		cur.execute("""
	CREATE TABLE IF NOT EXISTS ranking_param_data (
		game TEXT NOT NULL,
		pid TEXT NOT NULL,
		rank INTEGER NOT NULL,
		category INTEGER NOT NULL,
		data BLOB
	)""")
		cur.execute("""
	CREATE TABLE IF NOT EXISTS ranking_meta (
		game TEXT NOT NULL,
		pid TEXT NOT NULL,
		rank INTEGER NOT NULL,
		category INTEGER NOT NULL,
		data_id INTEGER,
		size INTEGER,
		name TEXT,
		data_type INTEGER,
		meta_binary BLOB,
		-- TODO add permisions
		create_time INTEGER,
		update_time INTEGER
		-- TODO add tags
		-- TODO add ratings
	)""")

		f = open('../find-nex-servers/nexwiiu.json')
		nex_wiiu_games = json.load(f)["games"]
		f.close()

		wiiu_games = requests.get('https://kinnay.github.io/data/wiiu.json').json()['games']

		log_file = open("log.txt", "a", encoding="utf-8")

		for i, game in enumerate(nex_wiiu_games):
			print_and_log("%s (%d out of %d)" % (game["name"].replace('\n', ' '), i, len(nex_wiiu_games)), log_file)

			pretty_game_id = hex(game['aid'])[2:].upper().rjust(16, "0")

			# If anything already exists for this game ignore
			#if len(cur.execute("SELECT rank FROM ranking WHERE game = ? LIMIT 1", (pretty_game_id,)).fetchall()) > 0:
			#	continue

			nas = nnas.NNASClient()
			nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
			nas.set_title(game["aid"], game["av"])
			nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)

			access_token = await nas.login(USERNAME, PASSWORD)

			nex_token = await nas.get_nex_token(access_token.token, game["id"])

			nex_version = game['nex'][0][0] * 10000 + game['nex'][0][1] * 100 + game['nex'][0][2]

			# Check if nexds is loaded
			has_datastore = bool([g for g in wiiu_games if g['aid'] == game['aid']][0]['nexds'])

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

			valid_categories = []
			num_tested = 0

			s = settings.default()
			s.configure(game["key"], nex_version)
			async with backend.connect(s, nex_token.host, nex_token.port) as be:
				async with be.login(str(nex_token.pid), nex_token.password) as client:
					ranking_client = ranking.RankingClient(client)

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
							print_and_log("Found category %d" % category, log_file)
						except Exception:
							None

						num_tested += 1

						if num_tested % 10 == 0:
							print_and_log("Tested %d categories" % num_tested, log_file)

			subgroup_size = 10
			subgroup_size_groups = [valid_categories[i:i+subgroup_size] for i in range(0, len(valid_categories), subgroup_size)]

			db_lock = Lock()
			log_lock = Lock()

			for group in subgroup_size_groups:
				# Run categories in parallel
				processes = [Process(target=run_category_scrape, args=(category, db_lock, log_lock, s, nex_token.host, nex_token.port, nex_token.pid, nex_token.password, game, pretty_game_id, has_datastore, i, nex_wiiu_games)) for category in group]
				for p in processes:
					p.start()
				for p in processes:
					p.join()

		log_file.close()

	if sys.argv[1] == "fix_meta_binary":
		None

if __name__ == '__main__':
	anyio.run(main)