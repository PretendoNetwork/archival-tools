from pyctr.crypto.engine import CryptoEngine, Keyslot
from io import BytesIO
from typing import IO
import os

def readle(i: IO, s) -> int:
	return int.from_bytes(i.read(s), 'little')

def readbe(i: IO, s) -> int:
	return int.from_bytes(i.read(s), 'big')

class BOSSHeader:
	magic: str
	magic_num: int
	filesize: int
	unk_int: int # * BE bytes (well not BE but read as BE), does not seem to be a date
	reserved: int
	padding: int
	content_header_hash_type: int
	content_header_rsa_size: int
	initial_iv_bytes_part: bytes

	def load(self, fd: IO):
		with BytesIO(fd.read(self.SIZE)) as dt:
			self.magic = dt.read(4).decode('ascii')

			if self.magic != 'boss':
				raise Exception("boss header magic mismatch")

			self.magic_num = readbe(dt, 4)

			if self.magic_num != 0x10001:
				raise Exception("boss header magic number mismatch")

			self.filesize = readbe(dt, 4)
			self.unk_int = readbe(dt, 8)
			self.reserved = readbe(dt, 2)
			self.padding = readbe(dt, 2)
			self.content_header_hash_type = readbe(dt, 2)
			self.content_header_rsa_size = readbe(dt, 2)
			self.initial_iv_bytes_part = dt.read(12)

	SIZE = 40

class BOSSContentHeader:
	unk_0x10_bytes: bytes
	filepath_part: bytes
	sha256_hash: bytes
	signature: bytes

	def load(self, fd: IO):
		with BytesIO(fd.read(self.SIZE)) as dt:
			self.unk_0x10_bytes = dt.read(0x10)
			self.filepath_part = dt.read(2)
			self.sha256_hash = dt.read(0x20)
			self.signature = dt.read(0x100)

	SIZE = 0x132

class BOSSPayloadContentHeader:
	title_id: int
	unk0: bytes
	content_datatype: int
	payload_size: int
	ns_data_id: int
	maybe_version: int
	sha256_hash: bytes
	signature: bytes

	def load(self, fd: IO):
		with BytesIO(fd.read(self.SIZE)) as dt:
			self.title_id = readbe(dt, 8)
			self.unk0 = dt.read(4)
			self.content_datatype = readbe(dt, 4)
			self.ns_data_id = readbe(dt, 4)
			self.payload_size = readbe(dt, 4)
			self.maybe_version = readbe(dt, 4)
			self.sha256_hash = dt.read(0x20)
			self.signature = dt.read(0x100)

	SIZE = 0x13C

class BOSSFile:
	header: BOSSHeader
	content_header: BOSSContentHeader
	payload_content_header: BOSSPayloadContentHeader

	SIZE = BOSSHeader.SIZE + BOSSContentHeader.SIZE + BOSSPayloadContentHeader.SIZE

	payload: bytes

	def load(self, path: str):
		if not os.path.isfile(path):
			raise FileNotFoundError(path)

		siz = os.path.getsize(path)

		if siz <= self.SIZE:
			raise Exception("File is too short for a BOSS container")

		with open(path, "rb") as f:
			self.header = BOSSHeader()
			self.header.load(f)

			if siz < self.header.filesize:
				raise Exception(f"incomplete boss file. expected {self.header.filesize} bytes but for {siz} bytes instead")

			encrypted_payload = f.read() # * read remaining encrypted data

		ce = CryptoEngine()
		iv = self.header.initial_iv_bytes_part + b'\x00\x00\x00\x01'
		cipher = ce.create_ctr_cipher(Keyslot.BOSS, int.from_bytes(iv, "big"))
		dec_data = cipher.decrypt(encrypted_payload)
		with BytesIO(dec_data) as decrypted_payload:
			self.content_header = BOSSContentHeader()
			self.content_header.load(decrypted_payload)
			self.payload_content_header = BOSSPayloadContentHeader()
			self.payload_content_header.load(decrypted_payload)
			payload_pos = decrypted_payload.tell()
			self.payload = dec_data[payload_pos:payload_pos + self.payload_content_header.payload_size]

	def export_decrypted_payload(self, path: str):
		with open(path, "wb") as f:
			f.write(self.payload)
