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

if os.path.isfile('last-checked-timestamp.txt') and os.access('last-checked-timestamp.txt', os.R_OK):
	last_checked_timestamp_file = open('last-checked-timestamp.txt', 'r+')
	last_checked_timestamp = int(last_checked_timestamp_file.read())
else:
	last_checked_timestamp_file = open('last-checked-timestamp.txt', 'x+')
	last_checked_timestamp_file.write("135271087238")
	last_checked_timestamp = 135271087238 # * 4-11-2015 15:50:06, date of first objects upload

os.makedirs('./objects', exist_ok=True)
os.makedirs('./metadata', exist_ok=True)
os.makedirs('./custom-rankings', exist_ok=True)
os.makedirs('./buffer-queues', exist_ok=True)
os.makedirs('./course-records', exist_ok=True)

def should_download_object(data_id: int, expected_object_size: int, expected_object_version: int) -> bool:
	object_path = './objects/%d_v%d.bin' % (data_id, expected_object_version)
	metadata_path = './metadata/%d_v%d.json.gz' % (data_id, expected_object_version)
	custom_rankings_path = './custom-rankings/%d_v%d.json.gz' % (data_id, expected_object_version)
	buffer_queues_path = './buffer-queues/%d_v%d.json.gz' % (data_id, expected_object_version)
	course_records_path = './course-records/%d_v%d.json.gz' % (data_id, expected_object_version)

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

async def write_compressed_json(path: str, data: dict):
	with gzip.open(path, 'wb', compresslevel=6) as metadata_file:
		metadata_file.write(json.dumps(data).encode('utf-8'))

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

	files = [
		('./metadata/%d_v%d.json.gz' % (data_id, object_version), metadata),
		('./custom-rankings/%d_v%d.json.gz' % (data_id, object_version), custom_rankings),
		('./buffer-queues/%d_v%d.json.gz' % (data_id, object_version), buffer_queues),
		('./course-records/%d_v%d.json.gz' % (data_id, object_version), course_records),
	]

	# * Write all files at once
	async with anyio.create_task_group() as tg:
		for f in files:
			path, data = f
			tg.start_soon(write_compressed_json, path, data)

async def main():
	s = settings.default()
	s.configure("9f2b4678", 30810)

	async with backend.connect(s, "52.40.192.64", "59900") as be: # * Skip NNID API
		async with be.login(NEX_USERNAME, NEX_PASSWORD) as client:
			global datastore_smm_client
			datastore_smm_client = datastore_smm.DataStoreClientSMM(client)

			current_timestamp = last_checked_timestamp
			twelve_hours = 43200 # * Grab objects in 12 hour chunks
			max_timestamp = common.DateTime.make(2024, 4, 1).value() # * Stop searching after April 1st, 2024 (official shut down)
			keep_searching = True

			while keep_searching:
				start_datetime = common.DateTime(current_timestamp)
				end_datetime = common.DateTime.fromtimestamp(common.DateTime(current_timestamp).timestamp() + twelve_hours)

				print("Downloading next 100 objects between %s to %s" % (start_datetime, end_datetime))

				param = datastore_smm.DataStoreSearchParam()
				param.created_after = start_datetime
				param.created_before = end_datetime
				param.result_range.size = 100 # * Throws DataStore::InvalidArgument for anything higher than 100
				param.result_option = 0xFF

				search_object_response = await datastore_smm_client.search_object(param)
				objects = search_object_response.result

				print("Found %d objects" % len(objects))

				# * Process all objects at once
				async with anyio.create_task_group() as tg:
					for obj in objects:
						tg.start_soon(process_datastore_object, obj)

				last_checked_timestamp_file.seek(0)
				last_checked_timestamp_file.write(str(current_timestamp))

				last_object_upload_timestamp = objects[-1].create_time.value()

				if last_object_upload_timestamp >= max_timestamp:
					print("Max timestamp reached. Stop searching")
					keep_searching = False
				elif len(objects) == 100:
					print("More objects may be available, trying new offset!")
					# * Set new timestamp to the upload date of the last
					# * returned object, so we don't skip any
					current_timestamp = last_object_upload_timestamp
				else:
					print("No more objects available!")
					keep_searching = False

anyio.run(main)