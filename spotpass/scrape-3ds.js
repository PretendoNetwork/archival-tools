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
	await Promise.all(COUNTRIES.map(async (country) => {
		await scrapeCountry(country, downloadBase);
	}));
}

async function scrapeCountry(country, downloadBase) {
	await Promise.all(LANGUAGES.map(async (language) => {
		await scrapeLanguage(country, language, downloadBase);
	}));
}

async function scrapeLanguage(country, language, downloadBase) {
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
			// * Not sure any better way to do this.
			for (const file of files) {
				const parts = file.split('\t');
				const fileName = parts[0];

				// * There are 4 possible formats for NPDL URLs.
				// * This tries all of them, one after the other, from least
				// * specific to most specific. This should result in the most
				// * specific version of each file being downloaded, overwriting
				// * less specific ones. Not all files work with all formats, so
				// * we just have to try them all and pray.
				// * This is pretty slow, but it at least should get all the data.
				const downloadPath = `${downloadBase}/${country}/${language}/${app.app_id}/${task}/${fileName}.boss`;

				await downloadContentFile(`${NPDL_URL_BASE}/${app.app_id}/${task}/${fileName}`, downloadPath);
				await downloadContentFile(`${NPDL_URL_BASE}/${app.app_id}/${task}/${language}/${fileName}`, downloadPath);
				await downloadContentFile(`${NPDL_URL_BASE}/${app.app_id}/${task}/${language}_${country}/${fileName}`, downloadPath);
				await downloadContentFile(`${NPDL_URL_BASE}/${app.app_id}/${task}/${country}/${language}/${fileName}`, downloadPath);
			}
		}
	}
}

async function downloadContentFile(url, downloadPath) {
	const response = await axios.get(url, {
		responseType: 'arraybuffer',
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});

	if (response.status !== 200) {
		return;
	}

	const fileData = Buffer.from(response.data, 'binary');

	fs.writeFileSync(downloadPath, fileData);
}

module.exports = scrape3DS;