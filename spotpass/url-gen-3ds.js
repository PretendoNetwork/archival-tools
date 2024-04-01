const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const database = require('./database');

const NPFL_URL_BASE = 'https://npfl.c.app.nintendowifi.net/p01/filelist';
const NPDL_URL_BASE = 'https://npdl.cdn.nintendowifi.net/p01/nsa';

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'), // * Hey, it works lol
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function urlGen3DS(downloadBase) {
	let batch = await database.getNextBatch('ctr');

	while (batch.length !== 0) {
		await Promise.all(batch.map(async (task) => {
			await scrapeTask(downloadBase, task);
			await database.rowProcessed(task.id);
		}));

		batch = await database.getNextBatch('ctr');
	}
}

async function scrapeTask(downloadBase, task) {
	const response = await axios.get(`${NPFL_URL_BASE}/${task.app_id}/${task.task}?c=${task.country}&l=${task.language}`, {
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});

	if (!response.headers['content-type'] || !response.headers['content-type'].startsWith('text/plain')) {
		return;
	}
	console.log(`${NPFL_URL_BASE}/${task.app_id}/${task.task}?c=${task.country}&l=${task.language}`);

	fs.ensureDirSync(`${downloadBase}_fl/${task.country}/${task.language}/${task.app_id}/${task.task}`);
	fs.writeFileSync(`${downloadBase}_fl/${task.country}/${task.language}/${task.app_id}/${task.task}/filelist.txt`, response.data);

	const lines = response.data.split('\r\n').filter(line => line);
	const files = lines.splice(2)

	// * There's like 5 ways the 3DS can format these download URLs, just pray this works I guess.
	// * Not sure any better way to do this.
	for (const file of files) {
		const parts = file.split('\t');
		const fileName = parts[0];

		// * There are 5 possible formats for NPDL URLs.
		// * This tries all of them, one after the other, from least
		// * specific to most specific. This should result in the most
		// * specific version of each file being downloaded, overwriting
		// * less specific ones. Not all files work with all formats, so
		// * we just have to try them all and pray.
		// * This is pretty slow, but it at least should get all the data.

		let success = await console.log(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.country}/${task.language}/${fileName}`);

		if (success) {
			continue;
		}

		success = await console.log(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.language}_${task.country}/${fileName}`);

		if (success) {
			continue;
		}

		success = await console.log(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.country}/${fileName}`);

		if (success) {
			continue;
		}

		success = await console.log(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.language}/${fileName}`);

		if (success) {
			continue;
		}

		await console.log(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${fileName}`);
	}
}


async function main() {
	await database.connect();
	await urlGen3DS();
	await database.close();
}

main();
