const https = require('node:https');
const axios = require('axios');
const fs = require('fs-extra');
const database = require('./database');
const { create: xmlParser } = require('xmlbuilder2');

const NPFL_URL_BASE = 'https://npfl.c.app.nintendowifi.net/p01/filelist';
const NPDL_URL_BASE = 'https://npdl.cdn.nintendowifi.net/p01/nsa';

const httpsAgent = new https.Agent({
	rejectUnauthorized: false,
	cert: fs.readFileSync('./certs/wiiu-common.crt'), // * Hey, it works lol
	key: fs.readFileSync('./certs/wiiu-common.key'),
});

async function scrape3DS(downloadBase) {
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

	fs.ensureDirSync(`${downloadBase}/${task.country}/${task.language}/${task.app_id}/${task.task}`);
	fs.writeFileSync(`${downloadBase}/${task.country}/${task.language}/${task.app_id}/${task.task}/filelist.txt`, response.data);

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
		const downloadPath = `${downloadBase}/${task.country}/${task.language}/${task.app_id}/${task.task}/${fileName}.boss`;
		const headersPath = `${downloadBase}/${task.country}/${task.language}/${task.app_id}/${task.task}/${fileName}.boss_headers.txt`;

		let success = await downloadContentFile(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.country}/${task.language}/${fileName}`, downloadPath, headersPath);

		if (success) {
			fs.appendFile('scrape_data_3ds.csv', (`${task.app_id},${task.task},${fileName},${task.country},${task.language}\n`));
			return;
		}

		success = await downloadContentFile(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.language}_${task.country}/${fileName}`, downloadPath, headersPath);

		if (success) {
			fs.appendFile('scrape_data_3ds.csv', (`${task.app_id},${task.task},${fileName},${task.country},${task.language}\n`));
			return
		}

		success = await downloadContentFile(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.country}/${fileName}`, downloadPath, headersPath);

		if (success) {
			fs.appendFile('scrape_data_3ds.csv', (`${task.app_id},${task.task},${fileName},${task.country},${task.language}\n`));
			return
		}

		success = await downloadContentFile(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${task.language}/${fileName}`, downloadPath, headersPath);

		if (success) {
			fs.appendFile('scrape_data_3ds.csv', (`${task.app_id},${task.task},${fileName},${task.country},${task.language}\n`));
			return
		}

		success = await downloadContentFile(`${NPDL_URL_BASE}/${task.app_id}/${task.task}/${fileName}`, downloadPath, headersPath);

		if (success) {
			fs.appendFile('scrape_data_3ds.csv', (`${task.app_id},${task.task},${fileName},${task.country},${task.language}\n`));
		}
	}
}

async function downloadContentFile(url, downloadPath, headersPath) {
	const response = await axios.get(url, {
		responseType: 'arraybuffer',
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});

	if (response.status !== 200) {
		return false;
	}

	const fileData = Buffer.from(response.data, 'binary');
	const headersString = JSON.stringify(response.headers, null, 2);

	fs.writeFileSync(downloadPath, fileData);
	fs.writeFileSync(headersPath, headersString);

	return true;
}

module.exports = scrape3DS;
