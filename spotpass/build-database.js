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
			processed BOOLEAN DEFAULT FALSE,
			UNIQUE (platform, app_id, task, country, language)
		)
	`);

	const startTime = performance.now();

	const values = [];

	for (const app of apps) {
		for (const task of app.tasks) {
			for (const country of COUNTRIES) {
				for (const language of LANGUAGES) {
					values.push(`("${app.platform}", "${app.app_id}", "${task}", "${country}", "${language}")`);
				}
			}
		}
	}

	// * Inserting all rows at once is basically instant.
	// * No point in filtering since this isn't user input
	const query = `INSERT INTO tasks (platform, app_id, task, country, language) VALUES ${values.join(', ')} ON CONFLICT(platform, app_id, task, country, language) DO NOTHING`;

	await database.run(query);

	const endTime = performance.now();
	const executionTime = millisecondsToString(endTime - startTime);

	console.log(`Database built in ${executionTime}`);

	await database.close();
}

build();
