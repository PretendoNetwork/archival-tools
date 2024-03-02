import os
import sys
import anyio
import requests
from dotenv import load_dotenv
from nintendo.nex import backend, ranking, datastore, settings, prudp, authentication, rmc
from nintendo import nnas
from anynet import udp, tls, websocket, util, \
	scheduler, crypto, streams, queue
import hashlib
import hmac
import struct
import threading
import time
from multiprocessing import Process, Lock, Queue, Array
import json

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

async def main():
	nex_wiiu_games = requests.get('https://raw.githubusercontent.com/TheGreatRambler/kinnay.github.io/master/data/nexwiiu.json').json()['games']
	for game in nex_wiiu_games:
		print(game["name"])

		nas = nnas.NNASClient()
		nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
		nas.set_title(game["aid"], game["av"])
		nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)
		
		access_token = await nas.login(USERNAME, PASSWORD)
		
		nex_token = await nas.get_nex_token(access_token.token, game["id"])

		nex_version = game['nex'][0][0] * 10000 + game['nex'][0][1] * 100 + game['nex'][0][2]
		
		s = settings.default()
		s.configure(game["key"], nex_version)
		async with backend.connect(s, nex_token.host, nex_token.port) as be:
			async with be.login(str(nex_token.pid), nex_token.password) as client:
				ranking_client = ranking.RankingClient(client)

				valid_categories = []
				
				for category in range(100):
					try:
						time.sleep(0.1)

						order_param = ranking.RankingOrderParam()
						order_param.offset = 0
						order_param.count = 1

						rankings = await ranking_client.get_ranking(
							ranking.RankingMode.GLOBAL, #Get the global leaderboard
							category, #Category, this is 3-A (Magrove Cove)
							order_param,
							0, 0
						)

						# No exception, this is a valid category
						valid_categories.append(category)
					except Exception as e:
						print("Category %d didn't work: %s" % (category, str(e)))

				for category in valid_categories:
					order_param = ranking.RankingOrderParam()
					order_param.offset = 0
					order_param.count = 100

					rankings = await ranking_client.get_ranking(
						ranking.RankingMode.GLOBAL, #Get the global leaderboard
						category, #Category, this is 3-A (Magrove Cove)
						order_param,
						0, 0
					)

					print([entry.common_data.decode("ascii") for entry in rankings.data])
					

if __name__ == '__main__':
	anyio.run(main)