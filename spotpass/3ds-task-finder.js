const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const database = require('./database');
const apps = require('./ctr-boss-apps.json');

const NPFL_URL_BASE = 'https://npfl.c.app.nintendowifi.net/p01/filelist';
const TASK_SEARCH = 'FGONLYT'; // * For this example, I'm using the common FGONLYT task name, but there are other common task names that can be tested.

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'), // * Hey, it works lol
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function check3DS() {
	await database.connect();
	let batch = await database.getNextBatch('ctr');

	while (batch.length !== 0) {
		await Promise.all(batch.map(async (task) => {
			await findTask(task);
			await database.rowProcessed(task.id);
		}));

		batch = await database.getNextBatch('ctr');
	}
}

async function findTask(task) {
	const response = await axios.get(`${NPFL_URL_BASE}/${task.app_id}/${TASK_SEARCH}?c=${task.country}&l=${task.language}`, {
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});

	if (!response.headers['content-type'] || !response.headers['content-type'].startsWith('text/plain')) {
		return;
	} else {
        	for (const app of apps) {
        		if (app.app_id === task.app_id) {
        			if (!app.tasks.includes(TASK_SEARCH)) {
        				app.tasks.push(TASK_SEARCH);
						fs.writeJSONSync('./ctr-boss-apps.json', apps, {
							spaces: '\t'
						});
        			}
        		}
        	}
	}
}

async function find() {
	await check3DS();
	await database.close();
}

find();
