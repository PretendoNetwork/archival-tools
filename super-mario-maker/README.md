# Super Mario Maker
## Download all DataStore objects (makers, courses, etc) and their rankings/records

# Usage
Create `.env` from `example.env` and fill in your NEX details. There are multiple ways to get your NEX details. NEX details for both the WiiU and 3DS will work here:

- 3DS: To get your username and password from a 3DS, use this homebrew https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password
- WiiU: To get your username and password from a WiiU, use a proxy server like Fiddler or Charles and look for the response from https://account.nintendo.net/v1/api/provider/nex_token/@me. Your username is the `pid` field, and your password is the `password` field

Run `python3 archive.py`

# DataStore objects
This script downloads all available objects from DataStore, assuming the object is allowed to be returned. Not all objects may be downloaded, as DataStore may block public access to them. Not all objects may be Dream Worlds. To know what type of object a given object is, refer to it's metadata file

# DataStore object versions
DataStore objects can be updated. When this happens, the objects "version" number is incremented internally. The last number of the objects S3 key is the version number. DataStore only ever returns S3 URLs for the latest version, meaning all past versions are lost. This script will track the version number in the file name, allowing for multiple versions of the object to be downloaded if a newer object is uploaded, assuming this script is ran multiple times

# DataStore metadata
For every object downloaded, an associated metadata file is also saved. The contents of this file is the objects `DataStoreMetaInfo` serialized as JSON. To know which type of object a given object is, see `data_type` in the metadata file

```json
{
	"data_id": 915012,
	"owner_id": 1770180745,
	"size": 37788,
	"name": "Key to My Heart - by SethBling",
	"data_type": 12,
	"meta_binary": "000000020000000200000df4000000f800002f240000558c00000002c24ba7925b08b3bc62880bf37206322f004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004c006100200063006c00e90020006400650020006d006f006e00200063015300750072002000640065002000530065007400680042006c0069006e006700000000004c006c00610076006500730020007000720065006300690061006400610073002c002000640065002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000004b0065007900200074006f0020004d00790020004800650061007200740020002d002000620079002000530065007400680042006c0069006e0067000000000000",
	"permission": {
		"permission": 0,
		"recipients": []
	},
	"delete_permission": {
		"permission": 3,
		"recipients": []
	},
	"create_time": {
		"original_value": 135308465418,
		"standard": "2016-04-01 21:20:10"
	},
	"update_time": {
		"original_value": 135308465418,
		"standard": "2016-04-01 21:20:10"
	},
	"period": 64306,
	"status": 0,
	"referred_count": 0,
	"refer_data_id": 0,
	"flag": 3840,
	"referred_time": {
		"original_value": 135308465418,
		"standard": "2016-04-01 21:20:10"
	},
	"expire_time": {
		"original_value": 671075926016,
		"standard": "9999-12-31 00:00:00"
	},
	"tags": [
		"AYMHAAACAAADVHlDoA9gFw"
	],
	"ratings": [
		{
			"slot": 0,
			"info": {
				"total_value": 165896,
				"count": 165896,
				"initial_value": 0
			}
		},
		{
			"slot": 1,
			"info": {
				"total_value": 11908666,
				"count": 124183,
				"initial_value": 0
			}
		},
		{
			"slot": 2,
			"info": {
				"total_value": 23870,
				"count": 165896,
				"initial_value": 0
			}
		},
		{
			"slot": 3,
			"info": {
				"total_value": 1253174,
				"count": 165896,
				"initial_value": 0
			}
		},
		{
			"slot": 4,
			"info": {
				"total_value": 1229304,
				"count": 165896,
				"initial_value": 0
			}
		},
		{
			"slot": 5,
			"info": {
				"total_value": 137298,
				"count": 137298,
				"initial_value": 0
			}
		},
		{
			"slot": 6,
			"info": {
				"total_value": 847,
				"count": 847,
				"initial_value": 0
			}
		}
	]
}
```

# DataStore ratings
DataStore objects have any number of `ratings`. The meaning of each is context dependent, and changes based on the game and `data_type` of the object

# Custom Rankings
Super Mario Maker implements "custom rankings". These extend the DataStore rating system to more freely rank objects based on custom criteria, by using dynamically generated "application IDs". The meaning of each "application ID" also changes based on the `data_type` of the object, much like ratings

# Buffer Queues
Super Mario Maker implements "buffer queues" as a way to store some forms of arbitrary binary data for objects. An object can have any number of unique buffers in any of it's buffer queue slots. The meaning of each slot, and it's buffers, also changes based on the `data_type` of the object, much like ratings

# Course Records
A "course record" is downloaded for every object, even non-courses. This is expected to create many empty files, as only course objects have records. Since Super Mario Maker uses several different `data_type` values for courses, it's safer to just try to download a record for every object rather than check the objects type. This results in potentially millions of useless files, but ensures no data is missed