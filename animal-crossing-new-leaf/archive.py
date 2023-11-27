import os
import json
import anyio
from dotenv import load_dotenv
from nintendo.nex import backend, datastore, settings
from anynet import http

load_dotenv()

# Dump using https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password
NEX_USERNAME = os.getenv('NEX_3DS_USERNAME')
NEX_PASSWORD = os.getenv('NEX_3DS_PASSWORD')
datastore_client = None # Gets set later

if os.path.isfile('last-checked-offset.txt') and os.access('last-checked-offset.txt', os.R_OK):
	last_checked_offset_file = open('last-checked-offset.txt', 'r+')
	last_checked_offset = int(last_checked_offset_file.read())
else:
	last_checked_offset_file = open('last-checked-offset.txt', 'x+')
	last_checked_offset_file.write("0")
	last_checked_offset = 0

def is_valid_json_file(path: str) -> bool:
	try:
		with open(path, 'r') as json_file:
			# Attempt to load the JSON data
			json.load(json_file)
			return True
	except json.JSONDecodeError:
		return False
	except FileNotFoundError:
		return False

def should_download_object(data_id: int, expected_object_size: int, expected_object_version: int) -> bool:
	object_path = './objects/%d_v%d.bin' % (data_id, expected_object_version)
	metadata_path = './objects/%d_v%d_metadata.json' % (data_id, expected_object_version)

	if not os.path.exists(object_path):
		return True

	if not os.path.exists(metadata_path):
		return True

	if os.path.getsize(object_path) != expected_object_size:
		return True

	if not is_valid_json_file(metadata_path):
		return True

	return False # If nothing bails early, assume the object does not need to be redownloaded

async def process_datastore_object(obj: datastore.DataStoreMetaInfo):
	param = datastore.DataStorePrepareGetParam()
	param.data_id = obj.data_id

	get_object_response = await datastore_client.prepare_get_object(param)

	headers = {header.key: header.value for header in get_object_response.headers}
	s3_url = get_object_response.url
	object_version = int(s3_url.split('/')[-1].split('-')[1])

	if not should_download_object(get_object_response.data_id, get_object_response.size, object_version):
		# Object data already downloaded
		print("Skipping %d" % get_object_response.data_id)
		return

	response = await http.get(s3_url, headers=headers)

	object_file = open('./objects/%d_v%d.bin' % (get_object_response.data_id, object_version), 'wb')
	object_file.write(response.body)
	object_file.close()

	metadata = {
		'data_id': obj.data_id,
		'owner_id': obj.owner_id,
		'size': obj.size,
		'name': obj.name,
		'data_type': obj.data_type,
		'meta_binary': obj.meta_binary.hex(),
		'permission': {
			'permission': obj.permission.permission,
			'recipients': obj.permission.recipients
		},
		'delete_permission': {
			'permission': obj.delete_permission.permission,
			'recipients': obj.delete_permission.recipients
		},
		'create_time': {
			'original_value': obj.create_time.value(),
			'standard': obj.create_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		'update_time': {
			'original_value': obj.update_time.value(),
			'standard': obj.update_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		'period': obj.period,
		'status': obj.status,
		'referred_count': obj.referred_count,
		'refer_data_id': obj.refer_data_id,
		'flag': obj.flag,
		'referred_time': {
			'original_value': obj.referred_time.value(),
			'standard': obj.referred_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		'expire_time': {
			'original_value': obj.expire_time.value(),
			'standard': obj.expire_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
		},
		'tags': obj.tags,
		'ratings': [
			{
				'slot': rating.slot,
				'info': {
					'total_value': rating.info.total_value,
					'count': rating.info.count,
					'initial_value': rating.info.initial_value
				}
			}
			for rating in obj.ratings
		]
	}

	with open('./objects/%d_v%d_metadata.json' % (get_object_response.data_id, object_version), 'w') as metadata_file:
		json.dump(metadata, metadata_file, ensure_ascii=False)

async def main():
	os.makedirs('./objects', exist_ok=True)

	s = settings.default()
	s.configure("d6f08b40", 31017)

	async with backend.connect(s, "52.40.192.64", "60000") as be: # Skip NASC
		async with be.login(NEX_USERNAME, NEX_PASSWORD) as client:
			global datastore_client
			datastore_client = datastore.DataStoreClient(client)

			search_offset = last_checked_offset
			keep_searching = True

			while keep_searching:
				print("Downloading 100 objects from offset %d" % search_offset)

				param = datastore.DataStoreSearchParam()
				param.result_range.offset = search_offset
				param.result_range.size = 100 # Throws DataStore::InvalidArgument for anything higher than 100
				param.result_option = 0xFF

				search_object_response = await datastore_client.search_object(param)
				objects = search_object_response.result

				print("Found %d objects" % len(objects))

				# Process all objects at once
				async with anyio.create_task_group() as tg:
					for obj in objects:
						tg.start_soon(process_datastore_object, obj)

				last_checked_offset_file.seek(0)
				last_checked_offset_file.write(str(search_offset))

				if len(objects) == 100:
					print("More objects may be available, trying new offset!")
					search_offset += len(objects)
				else:
					print("No more objects available!")
					keep_searching = False

anyio.run(main)
