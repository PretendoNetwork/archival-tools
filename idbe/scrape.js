const https = require('node:https');
const fs = require('fs-extra');
const axios = require('axios');
const titles = require('./title-versions.json');

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'),
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

const failed = [];

async function downloadIcon(name, path, retries=0) {
	if (retries === 5) {
		failed.push(name);
		return;
	}

	try {
		// * ID field is unchecked, leave as 00 for now.
		// * Wii U server has icons for 3DS as well, leave as WUP for now.
		const response = await axios.get(`https://idbe-wup.cdn.nintendo.net/icondata/00/${name}.idbe`, {
			responseType: 'arraybuffer',
			validateStatus: () => {
				return true;
			},
			httpsAgent
		});

		// * Not all titles/versions have dedicated IDBE icons
		if (response.status !== 200) {
			return;
		}

		fs.writeFileSync(path, response.data);
	} catch {
		downloadIcon(name, path, retries++);
	}
}

async function main() {
	for (const titleID in titles) {
		const basePath = `./icons/${titleID}`;

		fs.ensureDirSync(basePath);

		// * Download the latest icon
		await downloadIcon(titleID, `${basePath}/latest.idbe`);

		// * Try all possible versions
		const versions = titles[titleID];

		for (const version of versions) {
			await downloadIcon(`${titleID}-${version}`, `${basePath}/${version}.idbe`);
		}

		// * Clean up empty folders
		const files = fs.readdirSync(basePath);

		if (files.length === 0) {
			fs.removeSync(basePath);
		}
	}

	console.log(failed);
}

main();