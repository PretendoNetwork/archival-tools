const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const { COUNTRIES, LANGUAGES } = require('./constants');
const apps = require('./ctr-boss-apps.json');

const NPFL_URL_BASE = 'https://npfl.c.app.nintendowifi.net/p01/filelist';
const TASKS = ['FGONLYT', 'news', 'data', 'TASK00', '0000001']; // * For this example, I'm using some common task names that are present in many games, but there are other ways this can be used, such as for matching tasks across different regions for a single game.

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'),
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function main() {
	for (const app of apps) {
		for (const task of TASKS) {
			// * Skip the task if the app already has it
			let titleHasTask = false;
			for (const appTask of app.tasks) {
				if (task.toLowerCase() == appTask.toLowerCase()) {
					titleHasTask = true;
					break;
				}
			}

			if (titleHasTask) {
				continue;
			}

			// * Most BOSS apps are region-agnostic, but some require
			// * specific combinations. Try every country/language
			// * combination until a task is found
			check_locales: for (const country of COUNTRIES) {
				for (const language of LANGUAGES) {
					if (await taskExists(app, task, country, language)) {
						console.log(`Task ${task} found for app id ${app.app_id}`);
						app.tasks.push(task);
						await fs.writeJSONSync('./ctr-boss-apps.json', apps, {
							spaces: '\t'
						});
						break check_locales;
					}
				}
			}
		}
	}
}

async function taskExists(app, task, country, language) {
	const response = await axios.get(`${NPFL_URL_BASE}/${app.app_id}/${task}?c=${country}&l=${language}`, {
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});

	if (!response.headers['content-type'] || !response.headers['content-type'].startsWith('text/plain')) {
		return false;
	}

	return true;
}

main();
