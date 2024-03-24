const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const { create: xmlParser } = require('xmlbuilder2');
const database = require('./database');

const TASK_SHEET_URL_BASE = 'https://npts.app.nintendo.net/p01/tasksheet/1';

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'),
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function urlGenWiiU(downloadBase) {
	let batch = await database.getNextBatch('wup');

	while (batch.length !== 0) {
		await Promise.all(batch.map(async (task) => {
			await scrapeTask(downloadBase, task);
			await database.rowProcessed(task.id);
		}));

		batch = await database.getNextBatch('wup');
	}
}

async function scrapeTask(downloadBase, task) {
	const response = await axios.get(`${TASK_SHEET_URL_BASE}/${task.app_id}/${task.task}?c=${task.country}&l=${task.language}`, {
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});

	if (!response.headers['content-type'] || !response.headers['content-type'].startsWith('application/xml')) {
		return;
	}
	console.log(`${TASK_SHEET_URL_BASE}/${task.app_id}/${task.task}?c=${task.country}&l=${task.language}`)

	fs.ensureDirSync(`${downloadBase}_fl/${task.country}/${task.language}/${task.app_id}/${task.task}`);
	fs.writeFileSync(`${downloadBase}_fl/${task.country}/${task.language}/${task.app_id}/${task.task}/tasksheet.xml`, response.data);

	const data = xmlParser(response.data).toObject();

	if (!data || !data.TaskSheet || !data.TaskSheet.Files || !data.TaskSheet.Files.File) {
		return;
	}

	let files = [];

	if (Array.isArray(data.TaskSheet.Files.File)) {
		files = data.TaskSheet.Files.File;
	} else {
		files.push(data.TaskSheet.Files.File);
	}

	for (const file of files) {
		await console.log(file.Url);
	}
}

async function main() {
	await database.connect();
	await urlGenWiiU();
	await database.close();
}

main();
