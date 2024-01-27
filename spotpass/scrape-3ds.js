const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const { COUNTRIES, LANGUAGES } = require('./constants');
const apps = require('./ctr-boss-apps.json');

const NPFL_URL_BASE = 'https://npfl.c.app.nintendowifi.net/p01/filelist';
const NPDL_URL_BASE = 'https://npdl.cdn.nintendowifi.net/p01/nsa';

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'), // * Hey, it works lol
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function scrape3DS(downloadBase) {
	for (const country of COUNTRIES) {
		for (const language of LANGUAGES) {
			for (const app of apps) {
				for (const task of app.tasks) {
					const response = await axios.get(`${NPFL_URL_BASE}/${app.app_id}/${task}?c=${country}&l=${language}`, {
						validateStatus: () => {
							return true;
						},
						httpsAgent
					});

					if (!response.headers['content-type'] || !response.headers['content-type'].startsWith('text/plain')) {
						continue;
					}

					fs.ensureDirSync(`${downloadBase}/${country}/${language}/${app.app_id}/${task}`);
					fs.writeFileSync(`${downloadBase}/${country}/${language}/${app.app_id}/${task}/filelist.txt`, response.data);

					const lines = response.data.split('\r\n').filter(line => line);
					const files = lines.splice(2)

					// * There's like 4 ways the 3DS can format these download URLs, just pray this works I guess.
					// * Not sure any better way to do this
					for (const file of files) {
						const parts = file.split('\t');
						const fileName = parts[0];

						const response = await axios.get(`${NPDL_URL_BASE}/${app.app_id}/${task}/${country}/${language}/${fileName}`, {
							responseType: 'arraybuffer',
							validateStatus: () => {
								return true;
							},
							httpsAgent
						});

						if (response.status !== 200) {
							continue;
						}

						const fileData = Buffer.from(response.data, 'binary');

						fs.writeFileSync(`${downloadBase}/${country}/${language}/${app.app_id}/${task}/${fileName}.boss`, fileData);
					}
				}
			}
		}
	}
}

module.exports = scrape3DS;