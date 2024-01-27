const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const { create: xmlParser } = require('xmlbuilder2');
const { COUNTRIES, LANGUAGES } = require('./constants');
const apps = require('./wup-boss-apps.json');

const TASK_SHEET_URL_BASE = 'https://npts.app.nintendo.net/p01/tasksheet/1';

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'),
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function scrapeWiiU(downloadBase) {
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
			const response = await axios.get(`${TASK_SHEET_URL_BASE}/${app.app_id}/${task}?c=${country}&l=${language}`, {
				validateStatus: () => {
					return true;
				},
				httpsAgent
			});

			if (!response.headers['content-type'] || !response.headers['content-type'].startsWith('application/xml')) {
				continue;
			}

			fs.ensureDirSync(`${downloadBase}/${country}/${language}/${app.app_id}/${task}`);
			fs.writeFileSync(`${downloadBase}/${country}/${language}/${app.app_id}/${task}/tasksheet.xml`, response.data);

			const data = xmlParser(response.data).toObject();

			if (!data || !data.TaskSheet || !data.TaskSheet.Files || !data.TaskSheet.Files.File) {
				continue;
			}

			let files = [];

			if (Array.isArray(data.TaskSheet.Files.File)) {
				files = data.TaskSheet.Files.File;
			} else {
				files.push(data.TaskSheet.Files.File);
			}

			for (const file of files) {
				const response = await axios.get(file.Url, {
					responseType: 'arraybuffer',
					httpsAgent
				});
				const fileData = Buffer.from(response.data, 'binary');

				fs.writeFileSync(`${downloadBase}/${country}/${language}/${app.app_id}/${task}/${file.Filename}.boss`, fileData);
			}
		}
	}
}

module.exports = scrapeWiiU;