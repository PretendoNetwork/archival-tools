import os
import anyio
import sqlite3
from dotenv import load_dotenv
from nintendo.nex import backend, datastore, settings

load_dotenv()

# * Dump using https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password
NEX_USERNAME = os.getenv("NEX_3DS_USERNAME")
NEX_PASSWORD = os.getenv("NEX_3DS_PASSWORD")
datastore_client = None # * Gets set later

conn = sqlite3.connect("./objects.db")
cursor = conn.cursor()

cursor.execute('''
	CREATE TABLE IF NOT EXISTS objects (
		id INTEGER PRIMARY KEY,
		processed BOOLEAN DEFAULT 0
	)
''')
conn.commit()

async def main():
	s = settings.default()
	s.configure("d6f08b40", 31017)

	async with backend.connect(s, "52.40.192.64", "60000") as be: # Skip NASC
		async with be.login(NEX_USERNAME, NEX_PASSWORD) as client:
			global datastore_client

			datastore_client = datastore.DataStoreClient(client)

			cursor.execute("SELECT *, MAX(id) FROM objects")
			start_data_id = cursor.fetchone()[0]

			if start_data_id is None:
				param = datastore.DataStoreSearchParam()

				param.result_order = 0 # * Ascending
				param.result_range.offset = 0
				param.result_range.size = 1
				param.result_option = 0

				search_object_response = await datastore_client.search_object(param)
				objects = search_object_response.result

				start_data_id = objects[0].data_id

			param = datastore.DataStoreSearchParam()

			param.result_order = 1 # * Descending
			param.result_range.offset = 0
			param.result_range.size = 1
			param.result_option = 0

			search_object_response = await datastore_client.search_object(param)
			objects = search_object_response.result

			end_data_id = objects[0].data_id

			await client.disconnect()

			for data_id in range(start_data_id, end_data_id+1):
				cursor.execute("INSERT INTO objects (id) VALUES (%d) ON CONFLICT (id) DO NOTHING" % data_id)

			conn.commit()

anyio.run(main)
