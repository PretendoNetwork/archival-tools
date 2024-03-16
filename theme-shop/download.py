import pycurl, os, sys, binascii, hashlib, struct
from io import BytesIO, SEEK_CUR
from boss import BOSSFile
from pathlib import Path
from pycurl import Curl

CTR_PEM_PATH = os.environ["CTR_PROD_3"]
OUTPUT_PATH = os.curdir
DL_MAX_CONN = 100

COUNTRIES = [
	'JP', 'AI', 'AG', 'AR', 'AW', 'BS', 'BB', 'BZ',
	'BO', 'BR', 'VG', 'CA', 'KY', 'CL', 'CO', 'CR',
	'DM', 'DO', 'EC', 'SV', 'GF', 'GD', 'GP', 'GT',
	'GY', 'HT', 'HN', 'JM', 'MQ', 'MX', 'MS', 'AN',
	'NI', 'PA', 'PY', 'PE', 'KN', 'LC', 'VC', 'SR',
	'TT', 'TC', 'US', 'UY', 'VI', 'VE', 'AL', 'AU',
	'AT', 'BE', 'BA', 'BW', 'BG', 'HR', 'CY', 'CZ',
	'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IS',
	'IE', 'IT', 'LV', 'LS', 'LI', 'LT', 'LU', 'MK',
	'MT', 'ME', 'MZ', 'NA', 'NL', 'NZ', 'NO', 'PL',
	'PT', 'RO', 'RU', 'RS', 'SK', 'SI', 'ZA', 'ES',
	'SZ', 'SE', 'CH', 'TR', 'GB', 'ZM', 'ZW', 'AZ',
	'MR', 'ML', 'NE', 'TD', 'SD', 'ER', 'DJ', 'SO',
	'AD', 'GI', 'GG', 'IM', 'JE', 'MC', 'TW', 'KR',
	'HK', 'MO', 'ID', 'SG', 'TH', 'PH', 'MY', 'CN',
	'AE', 'IN', 'EG', 'OM', 'QA', 'KW', 'SA', 'SY',
	'BH', 'JO', 'SM', 'VA', 'BM'
]

LANGUAGES = [ 'ja', 'en', 'fr', 'de', 'it', 'es', 'zh', 'ko', 'nl', 'pt', 'ru', 'zh_trad' ]

BOSS_IDS = {
	"EUR": "dMtiFHzm5OOf0y2O",
	"USA": "YapN7dMun6U6CVPx",
	"JPN": "110Rzo2E1vYSfAz6",
}

class DownloadTask:
	curl: Curl
	filename: str
	url: str
	region: str
	country: str
	language: str
	boss_id: str
	buffer: BytesIO
	header_buffer: BytesIO

	def __init__(self) -> None:
		self.curl = Curl()

class FileListEntry:
	itemcode_1: str
	price: str
	itemcode_2: str
	unk_id: str
	unknum: int
	timestamp: int

	@classmethod
	def parse_from_tsv(cls, tsv_line: list[str]):
		o = cls()
		o.itemcode_1 = tsv_line[0]
		o.price = tsv_line[1]
		o.itemcode_2 = tsv_line[2]
		o.unk_id = tsv_line[3]
		o.unknum = int(tsv_line[4])
		o.timestamp = int(tsv_line[5])
		return o

def parse_filelist(path: str) -> list[FileListEntry]:
	actualsize = os.path.getsize(path)

	with open(path, "rb") as f:
		sha1_hash = binascii.unhexlify(f.read(40))
		f.seek(2, SEEK_CUR)
		actual_data = f.read().decode("utf-8")

	# * first verify the sha1 checksum of the data
	checksum = hashlib.sha1(actual_data.encode("utf-8")).digest()
	if checksum != sha1_hash:
		raise Exception(f"hash mismatch, expected {sha1_hash.hex()} but got {checksum.hex()} instead")

	lines = actual_data.rstrip("\r\n").split("\r\n") # * CRLF? really?
	expected_content_len = int(lines[0].lstrip(" "))
	lines = lines[1:]

	if not lines:
		return []

	# * verify that the file is of correct size
	if actualsize != expected_content_len:
		raise Exception(f"File is incomplete; expected size is {expected_content_len}, got {actualsize} instead")

	return [ FileListEntry.parse_from_tsv(line.split("\t")) for line in lines ]

def align(x: int, y: int) -> int:
	return (x + y - 1) & ~(y - 1)

class ThmTopCategory:
	name: str # * utf-16 name, wchar[96] (192 bytes)
	category_id: int # * u32
	unknown_id: int # * u32
	image_descriptor: tuple[int, int]

	def __init__(self) -> None:
		self.image_descriptor = (0,0)

	@classmethod
	def from_bytes(cls, b: bytes):
		a = cls()
		dt = struct.unpack("<192s4I" if len(b) == 208 else "<192s2I", b)
		a.name = dt[0].decode("utf-16-le").rstrip("\x00")
		a.category_id = dt[1]
		a.unknown_id = dt[2]
		if len(b) == 208:
			a.image_descriptor = (dt[3], dt[4])
		return a

	def __str__(self) -> str:
		return \
			f"Name: {self.name}\n" \
			f"Category ID: {self.category_id}\n" \
			f"Unknown ID: {self.unknown_id}\n" + \
			(f"Has image: No\n" if self.image_descriptor == (0,0) else f"Yes, offset: {hex(self.image_descriptor[1])}, size: {hex(self.image_descriptor[0])}\n")


class ThmTopFile:
	basefile: BOSSFile

	version: int # * u8
	topimg_count: int # * u8
	home_theme_category_count: int # * u8, amount of theme categories with icons that are shown when theme shop is opened
	all_theme_category_count: int # * u8, amount of theme categories (without icons) that are shown when user presses "show more"
	all_theme_category_offset: int # * u32

	unk_int2: int # * u64 seems to be 0x1 for USA, and 0x2 for JPN, EUR, not sure what this is, doesn't affect data, maybe changes something when rendering on a 3ds

	topimg_descriptors: list[tuple[int, int]] # * these are pointing to the JPEG images shown on the top screen
	"""
	tuple of (size, offset)
	"""

	home_theme_categories: list[ThmTopCategory]
	all_theme_categories: list[ThmTopCategory]

	def __str__(self) -> str:
		return \
			f"Version: {self.version}\n" \
			f"Top image count: {self.topimg_count}\n" \
			f"Home theme category count: {self.home_theme_category_count}\n" \
			f"All theme category count: {self.all_theme_category_count}\n" \
			f"All theme category offset: 0x{self.all_theme_category_offset:X}\n" \
			f"Unknown: {self.unk_int2}\n"

	def load_from_bossfile(self, file: BOSSFile):
		self.basefile = file

		with BytesIO(file.payload) as payload:
			self.version = payload.read(1)[0]
			self.topimg_count = payload.read(1)[0]
			self.home_theme_category_count = payload.read(1)[0]
			self.all_theme_category_count = payload.read(1)[0]
			self.all_theme_category_offset = int.from_bytes(payload.read(4), "little")
			self.unk_int2 = int.from_bytes(payload.read(8), "little")

			self.topimg_descriptors = []

			for _ in range(self.topimg_count):
				b = struct.unpack("<2I", payload.read(8))
				self.topimg_descriptors.append(b)

			self.home_theme_categories = []

			for _ in range(self.home_theme_category_count):
				self.home_theme_categories.append(ThmTopCategory.from_bytes(payload.read(208)))

			self.all_theme_categories = []

			# * so, this is possible somehow
			if self.all_theme_category_count == 0:
				return

			# * must seek to the last category icon's end offset here, and align by 16, to get to the entire category list
			s = self.home_theme_categories[-1].image_descriptor
			allcategory_off = align(s[1] + s[0], 16)
			payload.seek(allcategory_off)

			for _ in range(self.all_theme_category_count):
				self.all_theme_categories.append(ThmTopCategory.from_bytes(payload.read(200)))

def create_thmtop_indata(region: str, boss_id: str, country: str, language: str):
	_url = f"https://npdl.cdn.nintendowifi.net/p01/nsa/{boss_id}/thmtop/{country}/{language}/top?tm=4"
	_path = os.path.join(OUTPUT_PATH, region, country, language, "thmtop.bin")
	return (_url, _path, boss_id, region, country, language)

def create_thmlist_indata(region: str, boss_id: str, country: str, language: str, category: str):
	_url = f"https://npdl.cdn.nintendowifi.net/p01/nsa/{boss_id}/thmlist/{country}/{language}/{category}?tm=4"
	_path = os.path.join(OUTPUT_PATH, region, country, language, f"ct_{category}.bin")
	return (_url, _path, boss_id, region, country, language)

def create_single_theme_detail_indata(region: str, boss_id: str, country: str, language: str, thmid: str):
	_url = f"https://npdl.cdn.nintendowifi.net/p01/nsa/{boss_id}/thmdtls/{country}/{language}/{thmid}?tm=4"
	_path = os.path.join(OUTPUT_PATH, region, country, language, "thmdtls", f"{thmid}.bin")
	return (_url, _path, boss_id, region, country, language)

def create_all_theme_detail_indata(region: str, boss_id: str, country: str, language: str, index: int):
	_url = f"https://npfl.c.app.nintendowifi.net/p01/filelist/{boss_id}/thmdtls?c={country}&l={language}&a3={index}"
	_path = os.path.join(OUTPUT_PATH, region, country, language, f"thmdtls_filelist_{index}.txt")
	return (_url, _path, boss_id, region, country, language)

def run_downloader(queue: list[tuple[str, str, str, str, str, str]], num_conn: int = 50):
	num_urls = len(queue)
	num_conn = min(num_conn, num_urls)

	handles: list[DownloadTask] = []
	lookup: dict[Curl, DownloadTask] = { }
	m = pycurl.CurlMulti()
	for _ in range(num_conn):
		c = DownloadTask()
		c.curl.setopt(pycurl.SSL_VERIFYHOST, False)
		c.curl.setopt(pycurl.SSL_VERIFYSTATUS, False)
		c.curl.setopt(pycurl.SSL_VERIFYPEER, False)
		c.curl.setopt(pycurl.SSLCERT, CTR_PEM_PATH)
		handles.append(c)
		lookup[c.curl] = c

	freelist = handles[:]
	num_processed = 0
	while num_processed < num_urls:
		while queue and freelist:
			url, fname, boss_id, region, country, language = queue.pop(0)
			c = freelist.pop()
			c.boss_id, c.region, c.country, c.language = boss_id, region, country, language;
			c.buffer = BytesIO()
			c.filename = fname
			c.header_buffer = BytesIO()
			c.curl.setopt(pycurl.URL, url)
			c.curl.setopt(pycurl.WRITEFUNCTION, c.buffer.write)
			c.curl.setopt(pycurl.HEADERFUNCTION, c.header_buffer.write)
			m.add_handle(c.curl)
			c.url = url
		while 1:
			ret, _ = m.perform()
			if ret != pycurl.E_CALL_MULTI_PERFORM:
				break
		while 1:
			num_q, ok_list, err_list = m.info_read()
			for y in ok_list:
				c = lookup[y]
				m.remove_handle(c.curl)
				if c.curl.getinfo(pycurl.RESPONSE_CODE) == 200:
					Path(os.path.dirname(c.filename)).mkdir(parents=True, exist_ok=True)
					with open(c.filename, "wb") as f:
						f.write(c.buffer.getvalue())
					with open(f"{c.filename}_headers.txt", "wb") as f:
						f.write(c.header_buffer.getvalue())
					print("200:", c.filename, c.url)
				c.header_buffer.close()
				del c.header_buffer
				c.buffer.close()
				del c.buffer
				freelist.append(c)
			for y, errno, errmsg in err_list:
				c = lookup[y]
				c.buffer.close()
				del c.buffer
				c.header_buffer.close()
				del c.header_buffer
				m.remove_handle(c.curl)
				sys.exit("Failed: {} {} {} {}".format(c.filename, c.url, errno, errmsg))
			num_processed = num_processed + len(ok_list) + len(err_list)
			if num_q == 0:
				break
		m.select(1.0)

	for c in handles:
		if hasattr(c, "buffer") and c.buffer is not None:
			c.buffer.close()
			del c.buffer
		if hasattr(c, "header_buffer") and c.header_buffer is not None:
			c.header_buffer.close()
			del c.header_buffer
		c.curl.close()
	m.close()

q = []

for region, boss_id in BOSS_IDS.items():
	for country in COUNTRIES:
		for language in LANGUAGES:
			for i in range(10):
				# * we'll do like 10 max because there is no way in hell there will be more than 2000 themes in any given region
				q.append(create_all_theme_detail_indata(region, boss_id, country, language, i))
			q.append(create_thmtop_indata(region, boss_id, country, language))

run_downloader(q, num_conn=DL_MAX_CONN)

q.clear()

for region in BOSS_IDS:
	countries_dled = os.listdir(os.path.join(OUTPUT_PATH, region))
	for country, country_path in [(x, os.path.join(OUTPUT_PATH, region, x)) for x in countries_dled]:
		languages_dled = os.listdir(country_path)
		for language, language_path in [(x, os.path.join(country_path, x)) for x in languages_dled]:
			thmtop_file = os.path.join(language_path, "thmtop.bin")
			thmdtls_filelists = [ os.path.join(language_path, x) for x in os.listdir(language_path) if x.startswith("thmdtls_filelist") and not "headers" in x ]

			if os.path.isfile(thmtop_file):
				bf = BOSSFile()
				bf.load(thmtop_file)
				thmtop = ThmTopFile()
				thmtop.load_from_bossfile(bf)

				for category in thmtop.all_theme_categories:
					q.append(create_thmlist_indata(region, BOSS_IDS[region], country, language, str(category.category_id)))

			if len(thmdtls_filelists) > 0:
				for thmdtls_filelist in thmdtls_filelists:
					filelist = parse_filelist(thmdtls_filelist)
					for filelist_entry in filelist:
						# * item code 1 and item code 2 are identical in all cases i tested
						# * however just to be safe, if they are differing, add them separately

						q.append(create_single_theme_detail_indata(region, BOSS_IDS[region], country, language, filelist_entry.itemcode_1))
						if filelist_entry.itemcode_1 != filelist_entry.itemcode_2:
							q.append(create_single_theme_detail_indata(region, BOSS_IDS[region], country, language, filelist_entry.itemcode_2))

run_downloader(q, num_conn=DL_MAX_CONN)
