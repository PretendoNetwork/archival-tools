import os
import json
import gzip
import anyio
import sqlite3
import asyncio
from dotenv import load_dotenv
from nintendo.nex import backend, datastore, settings
from anynet import http

load_dotenv()

# * Dump using https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password
NEX_USERNAME = os.getenv("NEX_3DS_USERNAME")
NEX_PASSWORD = os.getenv("NEX_3DS_PASSWORD")

datastore_client = None # * Gets set later
conn = None # * Gets set later
cursor = None # * Gets set later

def is_valid_json_file(path: str) -> bool:
	try:
		with open(path, "r") as json_file:
			# * Attempt to load the JSON data
			json.load(json_file)
			return True
	except json.JSONDecodeError:
		return False
	except FileNotFoundError:
		return False

def should_download_object(data_id: int, expected_object_size: int, expected_object_version: int) -> bool:
	object_path = "./objects/%d_v%d.bin" % (data_id, expected_object_version)
	metadata_path = "./objects/%d_v%d_metadata.json" % (data_id, expected_object_version)

	if not os.path.exists(object_path):
		return True

	if not os.path.exists(metadata_path):
		return True

	if os.path.getsize(object_path) != expected_object_size:
		return True

	if not is_valid_json_file(metadata_path):
		return True

	return False # * If nothing bails early, assume the object does not need to be redownloaded

async def process_datastore_object(obj: datastore.DataStoreMetaInfo):
	param = datastore.DataStorePrepareGetParam()
	param.data_id = obj.data_id

	get_object_response = await datastore_client.prepare_get_object(param)

	headers = {header.key: header.value for header in get_object_response.headers}
	s3_url = get_object_response.url
	object_version = int(s3_url.split("/")[-1].split("-")[1])

	if not should_download_object(get_object_response.data_id, get_object_response.size, object_version):
		# * Object data already downloaded
		print("Skipping %d" % get_object_response.data_id)
		return

	response = await http.get(s3_url, headers=headers)

	object_file = open("./objects/%d_v%d.bin" % (get_object_response.data_id, object_version), "wb")
	object_file.write(response.body)
	object_file.close()

	metadata = {
		"data_id": obj.data_id,
		"owner_id": obj.owner_id,
		"size": obj.size,
		"name": obj.name,
		"data_type": obj.data_type,
		"meta_binary": obj.meta_binary.hex(),
		"permission": {
			"permission": obj.permission.permission,
			"recipients": obj.permission.recipients
		},
		"delete_permission": {
			"permission": obj.delete_permission.permission,
			"recipients": obj.delete_permission.recipients
		},
		"create_time": {
			"original_value": obj.create_time.value(),
			"standard": obj.create_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		"update_time": {
			"original_value": obj.update_time.value(),
			"standard": obj.update_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		"period": obj.period,
		"status": obj.status,
		"referred_count": obj.referred_count,
		"refer_data_id": obj.refer_data_id,
		"flag": obj.flag,
		"referred_time": {
			"original_value": obj.referred_time.value(),
			"standard": obj.referred_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		"expire_time": {
			"original_value": obj.expire_time.value(),
			"standard": obj.expire_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		"tags": obj.tags,
		"ratings": [
			{
				"slot": rating.slot,
				"info": {
					"total_value": rating.info.total_value,
					"count": rating.info.count,
					"initial_value": rating.info.initial_value
				}
			}
			for rating in obj.ratings
		]
	}

	with gzip.open("./objects/%d_v%d_metadata.json.gz" % (get_object_response.data_id, object_version), "wb") as metadata_file:
		metadata_file.write(json.dumps(metadata).encode("utf-8"))

async def process_pending_objects():
	global cursor

	os.makedirs("./objects", exist_ok=True)

	cursor = conn.cursor()

	s = settings.default()
	s.configure("d6f08b40", 31017)

	async with backend.connect(s, "52.40.192.64", "60000") as be: # * Skip NASC
		async with be.login(NEX_USERNAME, NEX_PASSWORD) as client:
			global datastore_client

			datastore_client = datastore.DataStoreClient(client)

			while True:
				cursor.execute("SELECT id FROM objects WHERE processed = 0 LIMIT 100")
				rows = cursor.fetchall()

				if not rows:
					break

				print("Checking objects %d through %d" % (rows[0][0], rows[-1][0]))

				params = []

				for row in rows:
					data_id = row[0]
					param = datastore.DataStoreGetMetaParam()
					param.data_id = data_id
					param.result_option = 0xFF

					params.append(param)

				metas = await datastore_client.get_metas_multiple_param(params)
				objects = []

				for i in range(len(rows)):
					row = rows[i]
					data_id = row[0]

					obj = metas.infos[i]

					if obj.data_id == 0:
						cursor.execute("UPDATE objects SET processed = 1 WHERE id = %d" % data_id)
					else:
						objects.append(obj)

				async with anyio.create_task_group() as tg:
					for obj in objects:
						tg.start_soon(process_datastore_object, obj)

						cursor.execute("UPDATE objects SET processed = 1 WHERE id = %d" % obj.data_id)

				conn.commit()

			print("All objects processed")

async def main():
	global conn

	conn = sqlite3.connect("./objects.db")
	cursor = conn.cursor()

	cursor.execute("SELECT COUNT(*) FROM objects WHERE processed = 0")
	objects_remaining = cursor.fetchone()[0]

	print("Number of objects left to check: %d" % objects_remaining)

	await process_pending_objects()

	conn.close()

anyio.run(main)
