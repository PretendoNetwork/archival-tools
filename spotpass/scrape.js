const { performance } = require('node:perf_hooks');
const fs = require('fs-extra');
const scrapeWiiU = require('./scrape-wiiu');
const scrape3DS = require('./scrape-3ds');
const { COUNTRIES, LANGUAGES } = require('./constants');

async function scrape() {
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
}

function millisecondsToString(ms) {
	const seconds = Math.floor((ms / 1000) % 60);
	const minutes = Math.floor((ms / 1000 / 60) % 60);
	const hours = Math.floor((ms  / 1000 / 3600 ) % 24)

	return [
		`${hours.toString().padStart(2, '0')}h`,
		`${minutes.toString().padStart(2, '0')}m`,
		`${seconds.toString().padStart(2, '0')}s`
	].join(':');
}

scrape();