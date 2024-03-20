const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const database = require('./database');
const apps = require('./ctr-boss-apps.json');

const NPFL_URL_BASE = 'https://npfl.c.app.nintendowifi.net/p01/filelist';
const TASK_SEARCH = ['FGONLYT', 'news', 'data', 'TASK00', '0000001'] // * For this example, I'm using some common task names that are present in many games, but there are other ways this can be used, such as for matching tasks across different regions for a single game.

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
		}));

		batch = await database.getNextBatch('ctr');
	}
}

async function findTask(task) {
	for (const TASK of TASK_SEARCH) {
		const response = await axios.get(`${NPFL_URL_BASE}/${task.app_id}/${TASK}?c=${task.country}&l=${task.language}`, {
			validateStatus: () => {
				return true;
			},
			httpsAgent
		});

		if (!response.headers['content-type'] || !response.headers['content-type'].startsWith('text/plain')) {
			return;
		}
	    for (const app of apps) {
	    	if (app.app_id === task.app_id) {
	    		if (!app.tasks.includes(TASK)) {
	    			app.tasks.push(TASK);
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
