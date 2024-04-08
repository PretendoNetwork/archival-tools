const { performance } = require('node:perf_hooks');
const fs = require('fs-extra');
const scrapeWiiU = require('./scrape-wiiu');
const scrape3DS = require('./scrape-3ds');
const database = require('./database');
const { millisecondsToString } = require('./util');
const { COUNTRIES, LANGUAGES } = require('./constants');
const sqlite3 = require('sqlite3').verbose();

async function count() {
	// Open a database connection
	const db = new sqlite3.Database('tasks.db');

	// Run the query to get the count
	db.get('SELECT COUNT(*) AS count FROM tasks WHERE processed = FALSE', (err, row) => {
		if (err) {
			console.error(err.message);
			return;
		}

		console.log('Total tasks remaining:', row.count);
	});

	// Close the database connection
	db.close();
}

async function scrape() {
	await count();
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
