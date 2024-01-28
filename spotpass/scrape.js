const { performance } = require('node:perf_hooks');
const fs = require('fs-extra');
const scrapeWiiU = require('./scrape-wiiu');
const scrape3DS = require('./scrape-3ds');
const database = require('./database');
const { millisecondsToString } = require('./util');
const { COUNTRIES, LANGUAGES } = require('./constants');

async function scrape() {
	await database.connect();

	const time = new Date().toISOString().split('T')[0]; // * YYYY-MM-DD
	const downloadBase = `data/${time}`;

	for (const country of COUNTRIES) {
		for (const language of LANGUAGES) {
			fs.ensureDirSync(`${downloadBase}/${country}/${language}`);
		}
	}

	// * Run both at the same time
	const startTime = performance.now();

	await Promise.all([
		scrapeWiiU(downloadBase),
		scrape3DS(downloadBase)
	]);

	const endTime = performance.now();
	const executionTime = millisecondsToString(endTime - startTime);

	console.log(`Archived in ${executionTime}`);

	await database.close();
}

scrape();