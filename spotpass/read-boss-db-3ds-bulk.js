const fs = require('fs-extra');
const apps = require('./ctr-boss-apps.json');
const path = require('path');

const NPDL_REGEX = /(?:(?:npdl|npfl)\.(?:cdn|c\.app)\.nintendowifi\.net\/p01\/)?(?:nsa|filelist)\/([A-z0-9]{16})\/(\w*)/g;
//const NPDL_REGEX = /\/([A-z0-9]{16})\/(\w*)/g;

const directoryPath = './ctr_dumps/'; // Replace this with the path to your directory

const EXTENSION = '.bin';

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


const db = fs.readFileSync('./ctr_dumps/' + file, {
	encoding: 'utf8'
});
const matches = [...db.matchAll(NPDL_REGEX)];

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

if (apps.length-appsLengthBefore == 0 && newTasks == 0)
	console.log(`Nothing new here.`);
else
console.log(`Found ${apps.length-appsLengthBefore} new BOSS apps and ${newTasks} new tasks`);

fs.writeJSONSync('./ctr-boss-apps.json', apps, {
	spaces: '\t'
});
});
});
