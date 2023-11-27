# Animal Crossing: New Leaf
## Download all DataStore objects and their rankings

# Usage
Create `.env` from `example.env` and fill in your 3DS NEX details. To get your username and password, use this homebrew https://github.com/Stary2001/nex-dissector/tree/master/get_3ds_pid_password

Run `python3 archive.py`

# DataStore objects
This script downloads all available objects from DataStore, assuming the object is allowed to be returned. Not all objects may be downloaded, as DataStore may block public access to them. Not all objects may be Dream Worlds. To know what type of object a given object is, refer to it's metadata file

# DataStore object versions
DataStore objects can be updated. When this happens, the objects "version" number is incremented internally. The last number of the objects S3 key is the version number. DataStore only ever returns S3 URLs for the latest version, meaning all past versions are lost. This script will track the version number in the file name, allowing for multiple versions of the object to be downloaded if a newer object is uploaded, assuming this script is ran multiple times

# DataStore metadata
For every object downloaded, an associated metadata file is also saved. The contents of this file is the objects `DataStoreMetaInfo` serialized as JSON. To know which type of object a given object is, see `data_type` in the metadata file

```json
{
    "data_id": 1000001,
    "owner_id": 147204330,
    "size": 465056,
    "name": "Ninten@ninten",
    "data_type": 1,
    "meta_binary": "",
    "permission": {
        "permission": 0,
        "recipients": []
    },
    "delete_permission": {
        "permission": 3,
        "recipients": []
    },
    "create_time": {
        "original_value": 135337759007,
        "standard": "2016-11-01 05:04:31"
    },
    "update_time": {
        "original_value": 135337873922,
        "standard": "2016-11-02 01:08:02"
    },
    "period": 365,
    "status": 0,
    "referred_count": 973714,
    "refer_data_id": 0,
    "flag": 2,
    "referred_time": {
        "original_value": 135810914673,
        "standard": "2023-11-27 01:37:49"
    },
    "expire_time": {
        "original_value": 135877892465,
        "standard": "2024-11-26 01:37:49"
    },
    "tags": [
        "LNinten",
        "N00",
        "Paaron",
        "Pchloe",
        "Pkaren",
        "Pninten",
        "UL_A00010027",
        "UL_C0001",
        "V4254"
    ],
    "ratings": [
        {
            "slot": 0,
            "info": {
                "total_value": 0,
                "count": 0,
                "initial_value": 0
            }
        },
        {
            "slot": 1,
            "info": {
                "total_value": 0,
                "count": 0,
                "initial_value": 0
            }
        }
    ]
}
```