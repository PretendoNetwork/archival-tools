const fs = require('fs-extra');
const apps = require('./ctr-boss-apps.json');

const REGEX = /(?:npdl|npfl)\.(?:cdn|c\.app)\.nintendowifi\.net\/p01\/(?:nsa|filelist)\/([A-z0-9]{16})\/([\w-]*)/g;

const db = fs.readFileSync('./partitionA.bin', {
	encoding: 'utf8'
});
const matches = [...db.matchAll(REGEX)];

const appsLengthBefore = apps.length;
let newTasks = 0;

// * 256 possible tasks
for (const match of matches) {
	const appID = match[1];
	const task = match[2];

	let found = false;

	for (const app of apps) {
		if (app.app_id === appID) {
			found = true;

			if (!app.tasks.includes(task)) {
				app.tasks.push(task);
				newTasks += 1;
			}

			break;
		}
	}

	if (!found) {
		apps.push({
			app_id: appID,
			tasks: [ task ]
		});

		newTasks += 1;
	}
}

console.log(`Found ${apps.length-appsLengthBefore} new BOSS apps and ${newTasks} new tasks`);

fs.writeJSONSync('./ctr-boss-apps.json', apps, {
	spaces: '\t'
});
