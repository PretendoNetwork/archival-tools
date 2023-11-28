import os
import json
import gzip
import anyio
from dotenv import load_dotenv
from nintendo.nex import common, rmc, backend, datastore_smm, settings, streams
from anynet import http

load_dotenv()

"""
	Beginning of everything not implemented in NintendoClients
"""

class DataStoreGetCustomRankingByDataIdParam(common.Structure):
	def __init__(self):
		super().__init__()
		self.application_id = None
		self.data_id_list = None
		self.result_option = None
	
	def load(self, stream: streams.StreamIn, version: int):
		self.application_id = stream.u32()
		self.data_id_list = stream.list(stream.u64)
		self.result_option = stream.u8()
	
	def save(self, stream: streams.StreamIn, version: int):
		stream.u32(self.application_id)
		stream.list(self.data_id_list, stream.u64)
		stream.u8(self.result_option)

class DataStoreCustomRankingResult(common.Structure):
	def __init__(self):
		super().__init__()
		self.order = None
		self.score = None
		self.meta_info = None
	
	def load(self, stream: streams.StreamIn, version: int):
		self.order = stream.u32()
		self.score = stream.u32()
		self.meta_info = stream.extract(datastore_smm.DataStoreMetaInfo)
	
	def save(self, stream: streams.StreamIn, version: int):
		stream.u32(self.order)
		stream.u32(self.score)
		stream.add(self.meta_info)

class BufferQueueParam(common.Structure):
	def __init__(self):
		super().__init__()
		self.data_id = None
		self.slot = None
	
	def load(self, stream: streams.StreamIn, version: int):
		self.data_id = stream.u64()
		self.slot = stream.u32()
	
	def save(self, stream: streams.StreamIn, version: int):
		stream.u64(self.data_id)
		stream.u32(self.slot)

class DataStoreGetCourseRecordParam(common.Structure):
	def __init__(self):
		super().__init__()
		self.data_id = None
		self.slot = None
	
	def load(self, stream: streams.StreamIn, version: int):
		self.data_id = stream.u64()
		self.slot = stream.u8()
	
	def save(self, stream: streams.StreamIn, version: int):
		stream.u64(self.data_id)
		stream.u8(self.slot)

class DataStoreGetCourseRecordResult(common.Structure):
	def __init__(self):
		super().__init__()
		self.data_id = None
		self.slot = None
		self.first_pid = None
		self.best_pid = None
		self.best_score = None
		self.created_time = None
		self.updated_time = None
	
	def load(self, stream: streams.StreamIn, version: int):
		self.data_id = stream.u64()
		self.slot = stream.u8()
		self.first_pid = stream.u32()
		self.best_pid = stream.u32()
		self.best_score = stream.s32()
		self.created_time = stream.datetime()
		self.updated_time = stream.datetime()
	
	def save(self, stream: streams.StreamIn, version: int):
		stream.u64(self.data_id)
		stream.u8(self.slot)
		stream.u32(self.first_pid)
		stream.u32(self.best_pid)
		stream.s32(self.best_score)
		stream.datetime(self.created_time)
		stream.datetime(self.updated_time)

async def get_custom_ranking_by_data_id(param: DataStoreGetCustomRankingByDataIdParam) -> rmc.RMCResponse:
	# * --- request ---
	stream = streams.StreamOut(datastore_smm_client.settings)
	stream.add(param)
	data = await datastore_smm_client.client.request(datastore_smm_client.PROTOCOL_ID, 50, stream.get())

	# * --- response ---
	stream = streams.StreamIn(data, datastore_smm_client.settings)

	obj = rmc.RMCResponse()
	obj.ranking_result = stream.list(DataStoreCustomRankingResult)
	obj.results = stream.list(common.Result)

	return obj

async def get_buffer_queue(param: BufferQueueParam) -> list[bytes]:
	# * --- request ---
	stream = streams.StreamOut(datastore_smm_client.settings)
	stream.add(param)
	data = await datastore_smm_client.client.request(datastore_smm_client.PROTOCOL_ID, 54, stream.get())

	# * --- response ---
	stream = streams.StreamIn(data, datastore_smm_client.settings)

	result = stream.list(stream.qbuffer)

	return result

async def get_course_record(param: DataStoreGetCourseRecordParam) -> DataStoreGetCourseRecordResult:
	# * --- request ---
	stream = streams.StreamOut(datastore_smm_client.settings)
	stream.add(param)
	data = await datastore_smm_client.client.request(datastore_smm_client.PROTOCOL_ID, 72, stream.get())

	# * --- response ---
	stream = streams.StreamIn(data, datastore_smm_client.settings)

	result = stream.extract(DataStoreGetCourseRecordResult)

	return result

"""
	End of everything not implemented in NintendoClients
"""

# * Dump using https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password or from network dumps
NEX_USERNAME = os.getenv('NEX_USERNAME')
NEX_PASSWORD = os.getenv('NEX_PASSWORD')
datastore_smm_client = None # * Gets set later

KNOWN_BUFFER_QUEUE_SLOTS = [ 0, 2, 3 ]

# * These apply to all objects at all times
# * SMM has time-specific application IDs but these don't matter here
KNOWN_CUSTOM_RANKING_APPLICATION_IDS = [
	0,
	2400,
	3600,
	200000000,
	200002400,
	200003600,
	300000000,
	300002400,
	300003600,
]

KNOWN_COURSE_RECORD_SLOTS = [ 0 ]

# * 900000 is the first DataID in use
last_checked_id = 900000
last_valid_id = 900000

if os.path.isfile('last-checked-id.txt') and os.access('last-checked-id.txt', os.R_OK):
	last_checked_id_file = open('last-checked-id.txt', 'r+')
	last_checked_id = int(last_checked_id_file.read())
else:
	last_checked_id_file = open('last-checked-id.txt', 'x+')
	last_checked_id_file.write(str(last_valid_id))

if os.path.isfile('last-valid-id.txt') and os.access('last-valid-id.txt', os.R_OK):
	last_valid_id_file = open('last-valid-id.txt', 'r+')
	last_valid_id = int(last_valid_id_file.read())
else:
	last_valid_id_file = open('last-valid-id.txt', 'x+')
	last_valid_id_file.write(str(last_valid_id))

os.makedirs('./objects', exist_ok=True)
os.makedirs('./metadata', exist_ok=True)
os.makedirs('./custom-rankings', exist_ok=True)
os.makedirs('./buffer-queues', exist_ok=True)
os.makedirs('./course-records', exist_ok=True)

def is_valid_json_file(path: str) -> bool:
	try:
		with open(path, 'r') as json_file:
			# * Attempt to load the JSON data just to see if it's valid
			json.load(json_file)
			return True
	except json.JSONDecodeError:
		return False
	except FileNotFoundError:
		return False

def should_download_object(data_id: int, expected_object_size: int, expected_object_version: int) -> bool:
	object_path = './objects/%d_v%d.bin' % (data_id, expected_object_version)
	metadata_path = './metadata/%d_v%d.json' % (data_id, expected_object_version)
	custom_rankings_path = './custom-rankings/%d_v%d.json' % (data_id, expected_object_version)
	buffer_queues_path = './buffer-queues/%d_v%d.json' % (data_id, expected_object_version)
	course_records_path = './course-records/%d_v%d.json' % (data_id, expected_object_version)

	if not os.path.exists(object_path):
		return True

	if not os.path.exists(metadata_path):
		return True

	if not os.path.exists(custom_rankings_path):
		return True

	if not os.path.exists(buffer_queues_path):
		return True

	if not os.path.exists(course_records_path):
		return True

	if os.path.getsize(object_path) != expected_object_size:
		return True

	if not is_valid_json_file(metadata_path):
		return True

	return False # * If nothing bails early, assume the object does not need to be redownloaded

async def download_object_buffer_queues(buffer_queues: list[dict], data_id: int, slot: int):
	try:
		param = BufferQueueParam()
		param.data_id = data_id
		param.slot = slot

		response = await get_buffer_queue(param)

		buffer_queues.append({
			"slot": slot,
			"buffers": [buffer.hex() for buffer in response]
		})
	except:
		# * Eat errors
		# * SMM will throw errors if an object has no buffers in the slot
		return

async def download_object_custom_ranking(custom_rankings: list[dict], data_id: int, application_id: int):
	try:
		param = DataStoreGetCustomRankingByDataIdParam()
		param.application_id = application_id
		param.data_id_list = [data_id]
		param.result_option = 0

		response = await get_custom_ranking_by_data_id(param)

		custom_rankings.append({
			"application_id": application_id,
			"score": response.ranking_result[0].score
		})
	except:
		# * Eat errors
		# * SMM will throw errors if an object has no ranking in the application ID
		return

async def download_course_record(course_records: list[dict], data_id: int, slot: int):
	# * This is expected to fail OFTEN
	# * Only course objects have records
	try:
		param = DataStoreGetCourseRecordParam()
		param.data_id = data_id
		param.slot = slot

		response = await get_course_record(param)

		course_records.append({
			"slot": response.slot,
			"first_pid": response.first_pid,
			"best_pid": response.best_pid,
			"best_score": response.best_score,
			"created_time": {
				'original_value': response.created_time.value(),
				'standard': response.created_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
			},
			"updated_time": {
				'original_value': response.updated_time.value(),
				'standard': response.updated_time.standard_datetime().strftime("%Y-%m-%d %H:%M:%S")
			}
		})
	except:
		# * Eat errors
		# * SMM will throw errors if an object has no record in the slot
		return

async def process_datastore_object(obj: datastore_smm.DataStoreMetaInfo):
	param = datastore_smm.DataStorePrepareGetParam()
	param.data_id = obj.data_id

	get_object_response = await datastore_smm_client.prepare_get_object(param)

	s3_headers = {header.key: header.value for header in get_object_response.headers}
	s3_url = get_object_response.url
	data_id = get_object_response.data_id
	object_version = int(s3_url.split('/')[-1].split('-')[1].split('?')[0])

	if not should_download_object(data_id, get_object_response.size, object_version):
		# * Object data already downloaded
		print("Skipping %d" % data_id)
		return

	buffer_queues = []

	async with anyio.create_task_group() as tg:
		for slot in KNOWN_BUFFER_QUEUE_SLOTS:
			tg.start_soon(download_object_buffer_queues, buffer_queues, data_id, slot)

	custom_rankings = []

	async with anyio.create_task_group() as tg:
		for application_id in KNOWN_CUSTOM_RANKING_APPLICATION_IDS:
			tg.start_soon(download_object_custom_ranking, custom_rankings, data_id, application_id)

	course_records = []

	async with anyio.create_task_group() as tg:
		for slot in KNOWN_COURSE_RECORD_SLOTS:
			tg.start_soon(download_course_record, course_records, data_id, slot)

	s3_response = await http.get(s3_url, headers=s3_headers)

	object_file = open('./objects/%d_v%d.bin' % (data_id, object_version), 'wb')
	object_file.write(s3_response.body)
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

	with gzip.open('./metadata/%d_v%d.json.gz' % (data_id, object_version), 'wb') as metadata_file:
		metadata_file.write(json.dumps(metadata).encode('utf-8'))

	with gzip.open('./custom-rankings/%d_v%d.json.gz' % (data_id, object_version), 'wb') as custom_rankings_file:
		custom_rankings_file.write(json.dumps(custom_rankings).encode('utf-8'))

	with gzip.open('./buffer-queues/%d_v%d.json.gz' % (data_id, object_version), 'wb') as buffer_queues_file:
		buffer_queues_file.write(json.dumps(buffer_queues).encode('utf-8'))

	with gzip.open('./course-records/%d_v%d.json.gz' % (data_id, object_version), 'wb') as course_records_file:
		course_records_file.write(json.dumps(course_records).encode('utf-8'))

async def download_objects_chunk(valid_data_ids: list[int], data_ids: list[int]):
	first = data_ids[0]
	last = data_ids[-1]

	print("Checking objects %d-%d" % (first, last))

	param = datastore_smm.DataStoreGetMetaParam()
	param.result_option = 0xFF

	get_metas_response = await datastore_smm_client.get_metas(data_ids, param)
	objects = [obj for obj in get_metas_response.info if obj.data_id != 0]

	print("Found %d valid objects for IDs %d-%d" % (len(objects), first, last))

	if len(objects) > 0:
		# * Process all objects at once
		async with anyio.create_task_group() as tg:
			for obj in objects:
				valid_data_ids.append(obj.data_id)
				tg.start_soon(process_datastore_object, obj)

async def main():
	s = settings.default()
	s.configure("9f2b4678", 30810)

	async with backend.connect(s, "52.40.192.64", "59900") as be: # * Skip NNID API
		async with be.login(NEX_USERNAME, NEX_PASSWORD) as client:
			global datastore_smm_client
			global last_checked_id
			global last_valid_id

			datastore_smm_client = datastore_smm.DataStoreClientSMM(client)

			current_data_id = last_checked_id
			keep_searching = True
			chunk_size = 100
			number_of_chunks = 20

			while keep_searching:
				data_id_chunks = []

				for i in range(number_of_chunks):
					chunk_start_data_id = current_data_id + (i * chunk_size)
					chunk_end_data_id = chunk_start_data_id+chunk_size
					data_id_chunks.append(list(range(chunk_start_data_id, chunk_end_data_id)))

				final_chunk_last_id = data_id_chunks[-1][-1]
				valid_data_ids = []

				async with anyio.create_task_group() as tg:
					for data_id_chunk in data_id_chunks:
						tg.start_soon(download_objects_chunk, valid_data_ids, data_id_chunk)

				last_checked_id_file.seek(0)
				last_checked_id_file.write(str(current_data_id))

				last_valid_id_file.seek(0)
				last_valid_id_file.write(str(last_valid_id))

				"""
				As of November 27th 2023, DataID 69693094 is
				the last DataID in use. This may change, so
				as a buffer we check until DataID 69700000.
				This should be enough room, as I doubt 6906
				new users will join before shut down
				"""
				if final_chunk_last_id < 69_700_000:
					print("More objects may be available, trying new range")
					current_data_id = final_chunk_last_id+1
				else:
					print("DataID 69700000 reached. Assuming no more objects")
					keep_searching = False

				"""
				Store the last VALID DataID as well so that once
				this script is done, we can use this as the new
				starting ID to get any new maker objects without
				needing to check ALL objects again
				"""
				if len(valid_data_ids) > 0 and max(valid_data_ids) != 0:
					last_valid_id = max(valid_data_ids)

anyio.run(main)