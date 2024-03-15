# Nintendo 3DS Theme Shop

## Prerequisites
* Python
* libcurl 7.19.0 or greater
* 3DS Common Prod Cert from any 3DS system
* boot9.bin from any 3DS system
## Usage

1. Create `.env` and fill in the path leading to your 3DS common prod cert and the path leading to `boot9`. It should look something like this:

```
CTR_PROD_3=/path/to/your/3ds_common_cert.pem
BOOT9_PATH=/path/to/your/boot9.bin
```
2. Run `pip install -r requirements.txt` to install dependencies
3. Run `python3 download.py`
