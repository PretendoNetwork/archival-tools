const fs = require('fs-extra');
const apps = require('./wup-boss-apps.json');
const path = require('path');

const TASK_SIZE = 0x1000; // * Size of each task entry
const OFFSET_BASE = 0x103; // * Seems to have a 0x103 header

const VALID_APP_ID_REGEX = /[A-z0-9]{16}/;

const directoryPath = './wiiu_dumps/';

const EXTENSION = '.db';

fs.readdir(directoryPath, (err, files) => {
    if (err) {
        console.error('Error reading directory:', err);
        return;
    }

    const targetFiles = files.filter(file => {
        return path.extname(file).toLowerCase() === EXTENSION;
    });

    targetFiles.forEach(file => {
        console.log(file);

// * task.db is a database of all registered BOSS tasks for a user.
// * The file is preallocated to 0x00100103 bytes. Each task entry
// * is 0x1000 bytes, so removing the first 0x103 bytes from the
// * file (which is mostly empty) results in 256 possible slots for
// * tasks.
const db = fs.readFileSync('./wiiu_dumps/' + file);

const appsLengthBefore = apps.length;
let newTasks = 0;

// * 256 possible tasks
for (let i = 0; i < 256; i++) {
	const offset = OFFSET_BASE + (i * TASK_SIZE);
	const entry = db.subarray(offset, offset + TASK_SIZE);

	const task = entry.subarray(0x21, 0x2A).toString().replace(/\0/g, '');
	const appID = entry.subarray(0x7C1, 0x7D1).toString().replace(/\0/g, '');

	// * Not all entries are populated
	if (!task || !appID) {
		continue;
	}

	// * Not all BOSS tasks are for downloading content from the BOSS server.
	// * Some tasks upload content, some tasks download from a 3rd party server,
	// * etc. In these cases, there is no application ID in the entry. I'm sure
	// * there's some way to detect this in the entry, like through some flags,
	// * but this is enough for our purposes
	if (!VALID_APP_ID_REGEX.test(appID)) {
		continue;
	}

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

if (apps.length-appsLengthBefore == 0 && newTasks == 0)
	console.log(`Nothing new here.`);
else
console.log(`Found ${apps.length-appsLengthBefore} new BOSS apps and ${newTasks} new tasks`);

fs.writeJSONSync('./wup-boss-apps.json', apps, {
	spaces: '\t'
});
});
});
