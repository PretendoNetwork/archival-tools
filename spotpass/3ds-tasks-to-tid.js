const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const { create: xmlParser } = require('xmlbuilder2');
const { COUNTRIES, LANGUAGES } = require('./constants');
const apps = require('./ctr-boss-apps.json');

const TASK_SHEET_URL_BASE = 'https://npts.app.nintendo.net/p01/tasksheet/1';

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'),
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function main() {
	for (const app of apps) {
		if (app.title_id) {
			// * Skip any titles who already have this set.
			// * This includes those set to "unknown"
			continue;
		}

		// * Many nested loops are used here.
		// * If a title ID is found, we need
		// * to bail out of them all
		let deepExit = false;

		for (const country of COUNTRIES) {
			if (deepExit) {
				break;
			}

			for (const language of LANGUAGES) {
				if (deepExit) {
					break;
				}

				// * Most BOSS apps are region-agnostic, but some require
				// * specific combinations. Try every country/language
				// * combination until a title ID is found
				const titleID = await getTitleID(app, country, language);

				if (titleID) {
					app.title_id = titleID;
					deepExit = true;
				}
			}
		}

		// * If there still wasn't one set, assume the server couldn't
		// * handle the BOSS application
		if (!app.title_id) {
			app.title_id = 'unknown';
		}

		fs.writeJSONSync('./ctr-boss-apps.json', apps, {
			spaces: '\t'
		});
	}
}

async function getTitleID(app, country, language) {
	// * Sometimes a task may not work, so try them all
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

		const xml = xmlParser(response.data).toObject();

		if (!xml || !xml.TaskSheet || !xml.TaskSheet.TitleId) {
			continue;
		}

		const titleID = xml.TaskSheet.TitleId.toUpperCase();

		return titleID;
	}
}

main();