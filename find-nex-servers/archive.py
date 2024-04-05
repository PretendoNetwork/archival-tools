import os
import sys
import anyio
import asyncio
import requests
from dotenv import load_dotenv
from nintendo.nex import (
    backend,
    ranking,
    datastore,
    settings,
    prudp,
    authentication,
    rmc,
)
from nintendo import nnas, nasc
from anynet import udp, tls, util, scheduler
import hashlib
import hmac
import struct
import threading
import time
import multiprocessing
from multiprocessing import Process, Lock, Queue, Array
import json
import base64
import logging

import logging

logging.basicConfig(level=logging.FATAL)

load_dotenv()

DEVICE_ID = int(os.getenv("DEVICE_ID"))
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
SYSTEM_VERSION = int(os.getenv("SYSTEM_VERSION"), 16)
REGION_ID = int(os.getenv("REGION_ID"))
COUNTRY_NAME = os.getenv("COUNTRY")
LANGUAGE = os.getenv("LANGUAGE")

USERNAME = os.getenv("NEX_USERNAME")
PASSWORD = os.getenv("NEX_PASSWORD")

SERIAL_NUMBER_3DS = os.getenv("3DS_SERIAL_NUMBER")
MAC_ADDRESS_3DS = os.getenv("3DS_MAC_ADDRESS")
FCD_CERT_3DS = bytes.fromhex(os.getenv("3DS_FCD_CERT"))
USERNAME_3DS = int(os.getenv("3DS_USERNAME"))
USERNAME_HMAC_3DS = os.getenv("3DS_USERNAME_HMAC")

REGION_3DS = int(os.getenv("3DS_REGION"))
LANGUAGE_3DS = int(os.getenv("3DS_LANG"))

LIST_PATH = "3ds_list.txt"

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")


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
def range_test_access_key(
    i, syn_packet, host, port, title_id, num_tested_queue, found_key
):
    for number_key_base in range(268435456):
        number_key = number_key_base + i * 268435456

        if number_key_base % 1000000 == 0:
            num_tested_queue.put(1000000)

        string_key = hex(number_key)[2:].rjust(8, "0")
        if test_access_key(string_key, syn_packet):
            entry = "%s, %s, %s, %s, (%d)" % (
                hex(title_id)[2:].upper().rjust(16, "0"),
                hex(title_id)[-8:].upper(),
                string_key,
                host,
                port,
            )

            list_file = open(LIST_PATH, "a")
            list_file.write("%s\n" % entry)
            list_file.flush()
            list_file.close()

            print(entry)

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
        print("Tested %d in %f seconds" % (num_tested, cur - begin))


async def main():
    if sys.argv[1] == "get_access_keys":
        wiiu_games = requests.get("https://kinnay.github.io/data/wiiu.json").json()[
            "games"
        ]
        nex_wiiu_games = requests.get(
            "https://kinnay.github.io/data/nexwiiu.json"
        ).json()["games"]
        up_to_date_title_versions = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/archival-tools/master/idbe/title-versions.json"
        ).json()

        # Get NEX games
        nex_games = []
        for game in wiiu_games:
            if game["nex"]:
                # This server connects to NEX
                nex_games.append(game)

        # get possible access keys
        possible_access_keys = set()
        for game in nex_wiiu_games:
            possible_access_keys.add(game["key"])

        # Checked games
        checked_games = set()

        for game in nex_games:
            print("Attempting " + hex(game["aid"])[2:].upper())

            nex_version = (
                game["nex"][0][0] * 10000 + game["nex"][0][1] * 100 + game["nex"][0][2]
            )

            if (game["aid"], nex_version) in checked_games:
                continue

            # Kinnay JSON is not up to date
            title_version = max(
                up_to_date_title_versions[hex(game["aid"])[2:].upper().rjust(16, "0")]
            )

            nas = nnas.NNASClient()
            nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
            nas.set_title(game["aid"], title_version)
            nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)

            access_token = await nas.login(USERNAME, PASSWORD)

            # Guess game server IDs
            guess_game_server_id = int(hex(game["aid"])[-8:], 16)

            nex_token = None
            try:
                nex_token = await nas.get_nex_token(
                    access_token.token, guess_game_server_id
                )
            except nnas.NNASError:
                print(hex(game["aid"])[2:].upper() + " not connectable")
                checked_games.add((game["aid"], nex_version))
                continue

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
                                        syn_packet.syn_packet_options = (
                                            transport.packet_encoder.encode_options(
                                                packet
                                            )
                                        )
                                        syn_packet.syn_packet_header = (
                                            transport.packet_encoder.encode_header(
                                                packet,
                                                len(syn_packet.syn_packet_options),
                                            )
                                        )
                                        syn_packet.syn_packet_payload = packet.payload
                                        syn_packet.syn_packet_signature = (
                                            packet.signature
                                        )
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
                            entry = "%s, %s, %s, %s, (%d)" % (
                                hex(game["aid"])[2:].upper().rjust(16, "0"),
                                hex(game["aid"])[-8:].upper(),
                                string_key,
                                nex_token.host,
                                nex_token.port,
                            )

                            list_file = open(LIST_PATH, "a")
                            list_file.write("%s\n" % entry)
                            list_file.flush()
                            list_file.close()

                            print(entry)
                            done = True
                            break

                    if not done:
                        # Run everything in processes
                        num_tested_queue = Queue()

                        found_key_lock = Lock()
                        found_key = Array("c", 10, lock=found_key_lock)

                        processes = [
                            Process(
                                target=range_test_access_key,
                                args=(
                                    i,
                                    syn_packet,
                                    nex_token.host,
                                    nex_token.port,
                                    game["aid"],
                                    num_tested_queue,
                                    found_key,
                                ),
                            )
                            for i in range(16)
                        ]
                        # Queue for printing number tested
                        processes.append(
                            Process(
                                target=print_number_tested, args=(num_tested_queue,)
                            )
                        )
                        for p in processes:
                            p.start()
                        for p in processes:
                            p.join()

                        if found_key.value:
                            possible_access_keys.add(found_key.value.decode("utf-8"))
                else:
                    print("No SYN packet found")

            checked_games.add((game["aid"], nex_version))

    if sys.argv[1] == "get_access_keys_3ds":
        ds3_games = requests.get(
            "https://raw.githubusercontent.com/DaniElectra/kinnay-title-list/3ds/data/3ds.json"
        ).json()["games"]
        nex_ds3_games = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/nex-viewer/8dec0a64276bd508734276f3443639b68b808366/src/titles.json"
        ).json()
        up_to_date_title_versions = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/archival-tools/master/idbe/title-versions.json"
        ).json()

        # Get NEX games
        nex_games = []
        for game in ds3_games:
            if game["nex"]:
                # This server connects to NEX
                nex_games.append(game)

        # get possible access keys
        possible_access_keys = set()
        for game in nex_ds3_games:
            if game["access_key"]:
                possible_access_keys.add(game["access_key"])

        # Checked games
        checked_games = set()

        # Checked games AID
        list_file = open(LIST_PATH, "r")
        checked_games_aid = set(
            [int(line.split(",")[0].strip(), 16) for line in list_file.readlines()]
        )
        list_file.close()

        start_now = False

        for game in nex_games:
            print("Attempting " + hex(game["aid"])[2:].upper() + ", " + game["name"])

            if game["aid"] == 1125899908239360:
                start_now = True

            if not start_now:
                continue

            nex_version = (
                game["nex"][0][0] * 10000 + game["nex"][0][1] * 100 + game["nex"][0][2]
            )

            if (game["aid"], nex_version) in checked_games:
                continue

            if game["aid"] in checked_games_aid:
                continue

            # Kinnay JSON is not up to date
            key = hex(game["aid"])[2:].upper().rjust(16, "0")

            if not key in up_to_date_title_versions:
                continue

            title_version = max(up_to_date_title_versions[key])

            if game["av"] != title_version:
                print("This one is not the max title version, skip")
                continue

            nas = nasc.NASCClient()
            nas.set_title(game["aid"], title_version)
            nas.set_device(SERIAL_NUMBER_3DS, MAC_ADDRESS_3DS, FCD_CERT_3DS, "")
            nas.set_locale(REGION_3DS, LANGUAGE_3DS)
            nas.set_user(USERNAME_3DS, USERNAME_HMAC_3DS)

            guess_game_server_id = game["aid"] & 0xFFFFFFFF

            try:
                nex_token = await nas.login(guess_game_server_id)
            except nasc.NASCError:
                continue

            # Fake key to get SYN packet
            s = settings.load("3ds")
            s.configure("aaaaaaaa", nex_version, 1)
            s["prudp.version"] = 1

            # Firstly, obtain one SYN packet
            syn_packet = SynPacket()
            syn_packet_lock = threading.Lock()
            syn_packet_lock.acquire()

            if nex_token.host == "0.0.0.0" and nex_token.port == 0:
                print("This game doesn't actually support nex")
                continue

            # WiiU is UDP
            async with udp.connect(nex_token.host, nex_token.port) as socket:
                async with util.create_task_group() as group:
                    transport = prudp.PRUDPClientTransport(s, socket, group)

                    async def process_incoming():
                        while True:
                            data = await transport.socket.recv()

                            with util.catch():
                                packets = transport.packet_encoder.decode(data)
                                for packet in packets:
                                    if packet.type == prudp.TYPE_SYN:
                                        syn_packet.packet = packet
                                        syn_packet.syn_packet_options = (
                                            transport.packet_encoder.encode_options(
                                                packet
                                            )
                                        )
                                        syn_packet.syn_packet_header = (
                                            transport.packet_encoder.encode_header(
                                                packet,
                                                len(syn_packet.syn_packet_options),
                                            )
                                        )
                                        syn_packet.syn_packet_payload = packet.payload
                                        syn_packet.syn_packet_signature = (
                                            packet.signature
                                        )
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
                            client.resend_limit = 10

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
                            entry = "%s, %s, %s, %s, (%d)" % (
                                hex(game["aid"])[2:].upper().rjust(16, "0"),
                                hex(game["aid"])[-8:].upper(),
                                string_key,
                                nex_token.host,
                                nex_token.port,
                            )

                            list_file = open(LIST_PATH, "a")
                            list_file.write("%s\n" % entry)
                            list_file.flush()
                            list_file.close()

                            print(entry)
                            done = True
                            break

                    if not done:
                        # Run everything in processes
                        num_tested_queue = Queue()

                        found_key_lock = Lock()
                        found_key = Array("c", 10, lock=found_key_lock)

                        processes = [
                            Process(
                                target=range_test_access_key,
                                args=(
                                    i,
                                    syn_packet,
                                    nex_token.host,
                                    nex_token.port,
                                    game["aid"],
                                    num_tested_queue,
                                    found_key,
                                ),
                            )
                            for i in range(16)
                        ]
                        # Queue for printing number tested
                        processes.append(
                            Process(
                                target=print_number_tested, args=(num_tested_queue,)
                            )
                        )
                        for p in processes:
                            p.start()
                        for p in processes:
                            p.join()

                        if found_key.value:
                            possible_access_keys.add(found_key.value.decode("utf-8"))
                else:
                    print("No SYN packet found")

            checked_games.add((game["aid"], nex_version))

    if sys.argv[1] == "get_access_keys_3ds_no_cracking":
        ds3_games = requests.get(
            "https://raw.githubusercontent.com/DaniElectra/kinnay-title-list/3ds/data/3ds.json"
        ).json()["games"]
        nex_ds3_games = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/nex-viewer/8dec0a64276bd508734276f3443639b68b808366/src/titles.json"
        ).json()
        up_to_date_title_versions = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/archival-tools/master/idbe/title-versions.json"
        ).json()

        # Get NEX games
        nex_games = []
        for game in ds3_games:
            if game["nex"]:
                # This server connects to NEX
                nex_games.append(game)

        # get possible access keys
        possible_access_keys = set()
        for game in nex_ds3_games:
            if game["access_key"]:
                possible_access_keys.add(game["access_key"])

        # Checked games
        checked_games = set()

        for game in nex_games:
            print("Attempting " + hex(game["aid"])[2:].upper() + ", " + game["name"])

            nex_version = (
                game["nex"][0][0] * 10000 + game["nex"][0][1] * 100 + game["nex"][0][2]
            )

            if (game["aid"], nex_version) in checked_games:
                continue

            # Kinnay JSON is not up to date
            key = hex(game["aid"])[2:].upper().rjust(16, "0")

            if not key in up_to_date_title_versions:
                continue

            title_version = max(up_to_date_title_versions[key])

            if game["av"] != title_version:
                print("This one is not the max title version, skip")
                continue

            nas = nasc.NASCClient()
            nas.set_title(game["aid"], title_version)
            nas.set_device(SERIAL_NUMBER_3DS, MAC_ADDRESS_3DS, FCD_CERT_3DS, "")
            nas.set_locale(REGION_3DS, LANGUAGE_3DS)
            nas.set_user(USERNAME_3DS, USERNAME_HMAC_3DS)

            guess_game_server_id = game["aid"] & 0xFFFFFFFF

            try:
                nex_token = await nas.login(guess_game_server_id)
            except nasc.NASCError:
                continue

            # Fake key to get SYN packet
            s = settings.load("3ds")
            s.configure("aaaaaaaa", nex_version, 1)
            s["prudp.version"] = 1

            # Firstly, obtain one SYN packet
            syn_packet = SynPacket()
            syn_packet_lock = threading.Lock()
            syn_packet_lock.acquire()

            if nex_token.host == "0.0.0.0" and nex_token.port == 0:
                print("This game doesn't actually support nex")
                continue

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
                                        syn_packet.syn_packet_options = (
                                            transport.packet_encoder.encode_options(
                                                packet
                                            )
                                        )
                                        syn_packet.syn_packet_header = (
                                            transport.packet_encoder.encode_header(
                                                packet,
                                                len(syn_packet.syn_packet_options),
                                            )
                                        )
                                        syn_packet.syn_packet_payload = packet.payload
                                        syn_packet.syn_packet_signature = (
                                            packet.signature
                                        )
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
                            client.resend_limit = 10

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
                            entry = "%s, %s, %s, %s, (%d)" % (
                                hex(game["aid"])[2:].upper().rjust(16, "0"),
                                hex(game["aid"])[-8:].upper(),
                                string_key,
                                nex_token.host,
                                nex_token.port,
                            )

                            list_file = open(LIST_PATH, "a")
                            list_file.write("%s\n" % entry)
                            list_file.flush()
                            list_file.close()

                            print(entry)
                            done = True
                            break

                    if not done:
                        print("NO CRACKING!")
                else:
                    print("No SYN packet found")

            checked_games.add((game["aid"], nex_version))

    if sys.argv[1] == "complete_list":
        list_file = open(LIST_PATH, "r")
        list_lines = list_file.readlines()
        list_file.close()

        # Get list of games for their titles
        wiiu_games = requests.get("https://kinnay.github.io/data/wiiu.json").json()[
            "games"
        ]

        # Get base list of NEX games
        nex_wiiu_games = requests.get(
            "https://kinnay.github.io/data/nexwiiu.json"
        ).json()

        up_to_date_title_versions = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/archival-tools/master/idbe/title-versions.json"
        ).json()

        # Remove duplicates
        entries_raw = [
            [chunk.strip() for chunk in line.split(",")] for line in list_lines
        ]
        entries = []
        games_seen = set([])
        for entry in entries_raw:
            if not entry[0] in games_seen:
                games_seen.add(entry[0])
                entries.append(entry)

        new_list = {}
        new_list["categories"] = nex_wiiu_games["categories"]
        new_list["filters"] = nex_wiiu_games["filters"]
        new_list["fields"] = nex_wiiu_games["fields"]

        new_list["fields"].append(
            {"category": 0, "key": "av", "name": "Version", "state": False, "type": 4}
        )
        new_list["fields"].append(
            {"category": 0, "key": "nex", "name": "NEX", "state": True, "type": 6}
        )

        new_list["games"] = []

        for game in entries:
            try:
                title_version = max(up_to_date_title_versions[game[0]])

                # Have to search NEX version
                filtered_games = [
                    g for g in wiiu_games if g["aid"] == int(game[0], 16) and g["nex"]
                ]
                max_version = max(
                    [g["nex"][0] for g in filtered_games],
                    key=lambda x: tuple(-val for val in x),
                )
                game_entry = [g for g in filtered_games if g["nex"][0] == max_version][
                    0
                ]

                nex_version = (
                    game_entry["nex"][0][0] * 10000
                    + game_entry["nex"][0][1] * 100
                    + game_entry["nex"][0][2]
                )

                nas = nnas.NNASClient()
                nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
                nas.set_title(int(game[0], 16), title_version)
                nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)

                access_token = await nas.login(USERNAME, PASSWORD)

                nex_token = await nas.get_nex_token(
                    access_token.token, int(game[1], 16)
                )

                s = settings.default()
                s.configure(game[2], nex_version)

                context = tls.TLSContext()
                async with rmc.connect(
                    s, nex_token.host, nex_token.port, context=context
                ) as client:
                    auth = authentication.AuthenticationClient(client)
                    login_obj = await auth.login(str(nex_token.pid))
                    branch, build = login_obj.server_name.split(" ")

                    new_list["games"].append(
                        {
                            "id": int(game[1], 16),
                            "aid": int(game[0], 16),
                            "av": title_version,
                            "name": game_entry["name"],
                            "addr": [nex_token.host, nex_token.port],
                            "key": game[2],
                            "branch": branch,
                            "build": build,
                            "nex": game_entry["nex"],
                        }
                    )

                print("Completed %s" % game[0])

            except Exception as e:
                print("Couldn't connect to %s: %s" % (game[0], str(e)))

        new_list["games"] = sorted(
            new_list["games"], key=lambda x: x["name"], reverse=False
        )

        nex_json = open("nexwiiu.json", "w")
        nex_json.write(json.dumps(new_list, indent=4))
        nex_json.close()

    if sys.argv[1] == "complete_list_3ds":
        list_file = open(LIST_PATH, "r")
        list_lines = list_file.readlines()
        list_file.close()

        ds3_games = requests.get(
            "https://raw.githubusercontent.com/DaniElectra/kinnay-title-list/3ds/data/3ds.json"
        ).json()["games"]
        nex_ds3_games = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/nex-viewer/8dec0a64276bd508734276f3443639b68b808366/src/titles.json"
        ).json()
        up_to_date_title_versions = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/archival-tools/master/idbe/title-versions.json"
        ).json()

        # Remove duplicates
        entries_raw = [
            [chunk.strip() for chunk in line.split(",")] for line in list_lines
        ]
        entries = []
        games_seen = set([])
        for entry in entries_raw:
            if not entry[0] in games_seen:
                games_seen.add(entry[0])
                entries.append(entry)

        new_list = {}

        new_list["games"] = []

        for game in entries:
            title_version = max(up_to_date_title_versions[game[0]])

            # Have to search NEX version
            filtered_games = [
                g for g in ds3_games if g["aid"] == int(game[0], 16) and g["nex"]
            ]
            max_version = max(
                [g["nex"][0] for g in filtered_games],
                key=lambda x: tuple(-val for val in x),
            )
            game_entry = [g for g in filtered_games if g["nex"][0] == max_version][
                0
            ]

            nex_version = (
                game_entry["nex"][0][0] * 10000
                + game_entry["nex"][0][1] * 100
                + game_entry["nex"][0][2]
            )


            new_list["games"].append(
                    {
                        "id": int(game[1], 16),
                        "aid": int(game[0], 16),
                        "av": title_version,
                        "name": game_entry["name"],
                        "addr": [game[3], int(game[4][1:-1])],
                        "key": game[2],
                        "nex": game_entry["nex"],
                        "has_datastore": "nexds" in game_entry,
                    }
                )

        new_list["games"] = sorted(
            new_list["games"], key=lambda x: x["name"], reverse=False
        )

        nex_json = open("nex3ds.json", "w")
        nex_json.write(json.dumps(new_list, indent=4))
        nex_json.close()

    if sys.argv[1] == "get_nonworking":
        f = open("nexwiiu.json")
        nex_wiiu_games_tested = json.load(f)["games"]
        f.close()

        wiiu_games = requests.get("https://kinnay.github.io/data/wiiu.json").json()[
            "games"
        ]
        up_to_date_title_versions = requests.get(
            "https://raw.githubusercontent.com/PretendoNetwork/archival-tools/master/idbe/title-versions.json"
        ).json()

        # Get NEX games not tested
        nex_games = []
        seen_nex_games = set()
        for game in wiiu_games:
            if (
                game["nex"]
                and len([g for g in nex_wiiu_games_tested if g["aid"] == game["aid"]])
                == 0
                and not game["aid"] in seen_nex_games
            ):
                # This server connects to NEX
                nex_games.append(game)
                seen_nex_games.add(game["aid"])

        # get possible access keys
        possible_access_keys = set()
        for game in nex_wiiu_games_tested:
            possible_access_keys.add(game["key"])

        for game in nex_games:
            name = [g for g in wiiu_games if g["aid"] == game["aid"]][0][
                "longname"
            ].replace("\n", " ")
            print("Attempting " + hex(game["aid"])[2:].upper() + " " + name)

            nex_version = (
                game["nex"][0][0] * 10000 + game["nex"][0][1] * 100 + game["nex"][0][2]
            )

            # Kinnay JSON is not up to date
            title_version = max(
                up_to_date_title_versions[hex(game["aid"])[2:].upper().rjust(16, "0")]
            )

            nas = nnas.NNASClient()
            nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
            nas.set_title(game["aid"], title_version)
            nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)

            access_token = await nas.login(USERNAME, PASSWORD)

            # Guess game server IDs
            guess_game_server_id = int(hex(game["aid"])[-8:], 16)

            nex_token = None
            try:
                nex_token = await nas.get_nex_token(
                    access_token.token, guess_game_server_id
                )
            except nnas.NNASError:
                list_file = open("failedlist.txt", "a", encoding="utf-8")
                list_file.write(
                    hex(game["aid"])[2:].upper()
                    + " "
                    + str(name)
                    + " failed get_nex_token\n"
                )
                list_file.flush()
                list_file.close()
                continue

            # Fake key to get SYN packet
            s = settings.default()
            s.configure("aaaaaaaa", nex_version)

            # Firstly, obtain one SYN packet
            syn_packet = SynPacket()
            syn_packet_lock = threading.Lock()
            syn_packet_lock.acquire()

            # WiiU is UDP
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
                                        syn_packet.syn_packet_options = (
                                            transport.packet_encoder.encode_options(
                                                packet
                                            )
                                        )
                                        syn_packet.syn_packet_header = (
                                            transport.packet_encoder.encode_header(
                                                packet,
                                                len(syn_packet.syn_packet_options),
                                            )
                                        )
                                        syn_packet.syn_packet_payload = packet.payload
                                        syn_packet.syn_packet_signature = (
                                            packet.signature
                                        )
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
                    print(
                        hex(game["aid"])[2:].upper()
                        + " "
                        + str(name)
                        + " succeeded send_syn"
                    )

                    # First test known keys
                    for string_key in possible_access_keys:
                        if test_access_key(string_key, syn_packet):
                            entry = "%s, %s, %s, %s, (%d)" % (
                                hex(game["aid"])[2:].upper().rjust(16, "0"),
                                hex(game["aid"])[-8:].upper(),
                                string_key,
                                nex_token.host,
                                nex_token.port,
                            )

                            list_file = open(LIST_PATH, "a")
                            list_file.write("%s\n" % entry)
                            list_file.flush()
                            list_file.close()

                            print(entry)
                            done = True
                            break

                    if not done:
                        # Run everything in processes
                        num_tested_queue = Queue()

                        found_key_lock = Lock()
                        found_key = Array("c", 10, lock=found_key_lock)

                        processes = [
                            Process(
                                target=range_test_access_key,
                                args=(
                                    i,
                                    syn_packet,
                                    nex_token.host,
                                    nex_token.port,
                                    game["aid"],
                                    num_tested_queue,
                                    found_key,
                                ),
                            )
                            for i in range(16)
                        ]
                        # Queue for printing number tested
                        processes.append(
                            Process(
                                target=print_number_tested, args=(num_tested_queue,)
                            )
                        )
                        for p in processes:
                            p.start()
                        for p in processes:
                            p.join()

                        if found_key.value:
                            possible_access_keys.add(found_key.value.decode("utf-8"))
                else:
                    list_file = open("failedlist.txt", "a", encoding="utf-8")
                    list_file.write(
                        hex(game["aid"])[2:].upper()
                        + " "
                        + str(name)
                        + " failed send_syn\n"
                    )
                    list_file.flush()
                    list_file.close()


if __name__ == "__main__":
    if sys.platform == "linux" or sys.platform == "linux2" or sys.platform == "darwin":
        multiprocessing.set_start_method("spawn")
    anyio.run(main)
