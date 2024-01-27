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
	await Promise.all([
		scrapeWiiU(downloadBase),
		scrape3DS(downloadBase)
	]);
}

scrape();