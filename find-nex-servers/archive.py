import os
import anyio
import requests
from dotenv import load_dotenv
from nintendo.nex import backend, ranking, datastore, settings, prudp
from nintendo import nnas
from anynet import udp, tls, websocket, util, \
	scheduler, crypto, streams, queue
import hashlib
import hmac
import struct
import threading
import time
from multiprocessing import Process, Lock, Queue, Array

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

class SynPacket:
	def __init__(self):
		self.packet = None
		self.syn_packet_options = None
		self.syn_packet_header = None
		self.syn_packet_payload = None
		self.syn_packet_signature = None

def test_access_key(string_key, syn_packet):
	key = hashlib.md5(string_key.encode()).digest()
	mac = hmac.new(key, digestmod=hashlib.md5)
	mac.update(syn_packet.syn_packet_header[4:])
	mac.update(b"")
	mac.update(struct.pack("<I", sum(string_key.encode())))
	mac.update(b"")
	mac.update(syn_packet.syn_packet_options)
	mac.update(syn_packet.syn_packet_payload)
	return mac.digest() == syn_packet.syn_packet_signature

# Test ALL keys
def range_test_access_key(i, syn_packet, host, port, title_id, num_tested_queue, found_key):
	for number_key_base in range(536870912):
		number_key = number_key_base + i * 536870912

		if number_key_base % 1000000 == 0:
			num_tested_queue.put(1000000)
			#cur = time.perf_counter()
			#print('Tested %d in %f seconds' % (number_key_base, cur - begin))

			#if thread_variables.done:
			#	# End processing
			#	break

		string_key = hex(number_key)[2:].rjust(8, '0')
		if test_access_key(string_key, syn_packet):
			entry = '%s, %s, %s, %s, (%d)' % (hex(title_id)[2:].upper().rjust(16, "0"), hex(title_id)[-8:].upper(), string_key, host, port)

			list_file = open("list.txt", "a")
			list_file.write('%s\n' % entry)
			list_file.flush()
			list_file.close()

			print(entry)
			#thread_variables.possible_access_keys.add(string_key)
			#thread_variables.done = True

			found_key.value = ("%s" % string_key).encode()

			num_tested_queue.put(-1)
			break

	num_tested_queue.put(-1)

def print_number_tested(num_tested_queue):
	begin = time.perf_counter()
	num_tested = 0
	num_sentinels = 0
	while True:
		num_tested_add = num_tested_queue.get()

		# Use sentinels
		if num_tested_add == -1:
			num_sentinels += 1
			if num_sentinels == 8:
				break

		num_tested += num_tested_add

		cur = time.perf_counter()
		print('Tested %d in %f seconds' % (num_tested, cur - begin))

		

async def main():
#	nas = nnas.NNASClient()
#	nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
#	nas.set_title(0x0005000010100600, 16)
#	nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)
#
#	access_token = await nas.login(USERNAME, PASSWORD)
#
#	nex_token = await nas.get_nex_token(access_token.token, 0x10100600)
#
#	s = settings.default()
#	s.configure('0f037f64', 30001)
#	async with backend.connect(s, nex_token.host, nex_token.port) as be:
#		async with be.login(str(nex_token.pid), nex_token.password) as client:
#			print("Connected to 0005000010100600")

	wiiu_games = requests.get('https://kinnay.github.io/data/wiiu.json').json()['games']
	nex_wiiu_games = requests.get('https://kinnay.github.io/data/nexwiiu.json').json()['games']
	up_to_date_title_versions = requests.get('https://raw.githubusercontent.com/PretendoNetwork/archival-tools/master/idbe/title-versions.json').json()

	# Get NEX games
	nex_games = []
	for game in wiiu_games:
		if game['nex']:
			# This server connects to NEX
			nex_games.append(game)

	# get possible access keys
	possible_access_keys = set()
	for game in nex_wiiu_games:
		possible_access_keys.add(game['key'])

	# Checked games
	checked_games = set()

	#nex_games = [{
	#	'aid': 0x000500001010EB00,
	#	'av': 64,
	#	'nex': [[3, 5, 4]]
	#}]
	#possible_access_keys = set(['0f037f64'])

	for game in nex_games:
		print("Attempting " + hex(game['aid'])[2:].upper())

		nex_version = game['nex'][0][0] * 10000 + game['nex'][0][1] * 100 + game['nex'][0][2]

		if (game['aid'], nex_version) in checked_games:
			continue

		# Kinnay JSON is not up to date
		title_version = max(up_to_date_title_versions[hex(game['aid'])[2:].upper().rjust(16, "0")])

		nas = nnas.NNASClient()
		nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
		nas.set_title(game['aid'], title_version)
		nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)

		access_token = await nas.login(USERNAME, PASSWORD)

		# Guess game server IDs
		guess_game_server_id = int(hex(game['aid'])[-8:], 16)

		nex_token = None
		try:
			nex_token = await nas.get_nex_token(access_token.token, guess_game_server_id)
		except nnas.NNASError:
			print(hex(game['aid'])[2:].upper() + " not connectable")
			checked_games.add((game['aid'], nex_version))
			continue

		#print(hex(game['aid'])[2:], title_version, hex(game['aid'])[-8:], nex_version)

		# Fake key to get SYN packet
		s = settings.default()
		s.configure("aaaaaaaa", nex_version)

		# Firstly, obtain one SYN packet
		syn_packet = SynPacket()
		syn_packet_lock = threading.Lock()
		syn_packet_lock.acquire()

		# WiiU is UDP
		async with udp.connect(nex_token.host, nex_token.port) as socket:
			async with util.create_task_group() as group:
				transport = prudp.PRUDPClientTransport(s, socket, group)

				async def process_incoming():
					while True:
						data = await transport.socket.recv()

						with util.catch(Exception):
							packets = transport.packet_encoder.decode(data)
							for packet in packets:
								if packet.type == prudp.TYPE_SYN:
									syn_packet.packet = packet
									syn_packet.syn_packet_options = transport.packet_encoder.encode_options(packet)
									syn_packet.syn_packet_header = transport.packet_encoder.encode_header(packet, len(syn_packet.syn_packet_options))
									syn_packet.syn_packet_payload = packet.payload
									syn_packet.syn_packet_signature = packet.signature
								else:
									await transport.process_packet(packet)

				transport.group.start_soon(process_incoming)

				client = prudp.PRUDPClient(s, transport, s["prudp.version"])
				with transport.ports.bind(client, type=10) as local_port:
					client.bind(socket.local_address(), local_port, 10)
					client.connect(socket.remote_address(), 1, 10)

					async with client:
						client.scheduler = scheduler.Scheduler(group)
						client.scheduler.start()

						client.resend_timeout = 0.05
						client.resend_limit = 0

						try:
							await client.send_syn()
							await client.handshake_event.wait()

							if client.state == prudp.STATE_CONNECTED:
								None

							syn_packet_lock.release()
						except RuntimeError:
							None

			syn_packet_lock.acquire()
			syn_packet_lock.release()

			done = False
			if syn_packet.syn_packet_header:
				# First test known keys
				for string_key in possible_access_keys:
					if test_access_key(string_key, syn_packet):
						entry = '%s, %s, %s, %s, (%d)' % (hex(game['aid'])[2:].upper().rjust(16, "0"), hex(game['aid'])[-8:].upper(), string_key, nex_token.host, nex_token.port)
						
						list_file = open("list.txt", "a")
						list_file.write('%s\n' % entry)
						list_file.flush()
						list_file.close()

						print(entry)
						done = True
						break

				if not done:
					#class ThreadVariables:
					#	def __init__(self):
					#		self.begin = time.perf_counter()
					#		self.num_tested = 0
					#		self.done = False
					#		self.file_writing_lock = threading.Lock()
					#		self.list_file = list_file
					#		self.possible_access_keys = possible_access_keys
					#thread_variables = ThreadVariables()

					# Run everything in processes
					num_tested_queue = Queue()

					found_key_lock = Lock()
					found_key = Array('c', 10, lock = found_key_lock)

					processes = [Process(target=range_test_access_key, args=(i, syn_packet, nex_token.host, nex_token.port, game['aid'], num_tested_queue, found_key)) for i in range(8)]
					# Queue for printing number tested
					processes.append(Process(target=print_number_tested, args=(num_tested_queue,)))
					for p in processes:
						p.start()
					for p in processes:
						p.join()

					if found_key.value:
						possible_access_keys.add(found_key.value.decode("utf-8"))

					#with ThreadPoolExecutor(max_workers=4) as executor:
					#	submissions = [executor.submit(range_test_access_key, i, thread_variables, deepcopy(syn_packet)) for i in range(0, 4)]
					#	concurrent.futures.wait(submissions)

					#num_tested = 0
			else:
				print("No SYN packet found")

		checked_games.add((game['aid'], nex_version))

	list_file.close()

if __name__ == '__main__':
	anyio.run(main)