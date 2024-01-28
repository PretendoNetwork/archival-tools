const { performance } = require('node:perf_hooks');
const database = require('./database');
const { millisecondsToString } = require('./util');
const { COUNTRIES, LANGUAGES } = require('./constants');
const appsWiiU = require('./wup-boss-apps.json');
const apps3DS = require('./ctr-boss-apps.json');

const apps = [
	...appsWiiU.map(app => {
		app.platform = 'wup';

		return app;
	}),
	...apps3DS.map(app => {
		app.platform = 'ctr';

		return app;
	})
];

async function build() {
	await database.connect();

	await database.exec(`
		CREATE TABLE IF NOT EXISTS tasks (
			id        INTEGER PRIMARY KEY,
			platform  TEXT,
			app_id    TEXT,
			task      TEXT,
			country   TEXT,
			language  TEXT,
			processed BOOLEAN
		)
	`);

	// * Clear all records before inserting new ones
	await database.exec('DELETE FROM tasks');

	// * Generating this database actually takes quite a bit of time.
	// * Run as much of this concurrently as possible to try and speed
	// * things up.
	const startTime = performance.now();

	await Promise.all(COUNTRIES.map(async (country) => {
		await insertCountry(country);
	}));

	const endTime = performance.now();
	const executionTime = millisecondsToString(endTime - startTime);

	console.log(`Database built in ${executionTime}`);

	await database.close();
}

async function insertCountry(country) {
	await Promise.all(LANGUAGES.map(async (language) => {
		await insertLanguage(country, language);
	}));
}

async function insertLanguage(country, language) {
	for (const app of apps) {
		for (const task of app.tasks) {
			// * Create a row for every possible task in every country/language
			await database.run(`
				INSERT INTO tasks (
					platform,
					app_id,
					task,
					country,
					language,
					processed
				)
				VALUES (
					?,
					?,
					?,
					?,
					?,
					FALSE
				)
			`, app.platform, app.app_id, task, country, language);
		}
	}
}

build();