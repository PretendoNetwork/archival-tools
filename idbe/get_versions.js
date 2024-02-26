const https = require('node:https');
const fs = require('fs-extra');
const axios = require('axios');
const cheerio = require('cheerio');
const { create: xmlParser } = require('xmlbuilder2');

const titles = {};

function addVersionsToTitle(titleID, versions) {
	if (!titles[titleID]) {
		titles[titleID] = [0]; // * Always check for version 0. This exists for lots of titles, but is never in any version lists
	}

	for (let version of versions) {
		version = Number(version);

		if (!titles[titleID].includes(version)) {
			titles[titleID].push(version);
		}
	}
}

async function scrapeWiiUBrew() {
	const response = await axios.get('https://wiiubrew.org/wiki/Title_database');
	const $ = cheerio.load(response.data);

	const tables = $('.wikitable.sortable');

	for (const table of tables) {
		const rows = $(table).find('tr');

		// * Start at 1 to skip the header
		for (let i = 1; i < rows.length; i++) {
			const row = rows[i];
			const sections = $(row).text().split('\n\n').map(section => section.trim());
			let titleID = sections[0].replace('-', '').toUpperCase();
			let versionsIndex;

			switch (titleID.substring(0, 8)) {
				case '00050010':
				case '0005001B':
				case '00050030':
				case '0005000C':
				case '0005000E':
				case '00000007':
				case '00070002':
				case '00070008':
					versionsIndex = 3;
					break;
				case '00050000':
				case '00050002':
					versionsIndex = 5;
					break;
				default:
					throw new Error(titleID);
			}

			const versions = sections[versionsIndex].split(',').map(version => {
				return version
					.trim()
					.replace('v', '')
					.split(' ')[0]
					.split('(')[0]
			}).filter(version => version);

			addVersionsToTitle(titleID, versions);

			// * Catch any versions assigned to updates or DLC which aren't assinged to the base title
			if (titleID.startsWith('0005000E') || titleID.startsWith('0005000C')) {
				titleID = `00050000${titleID.substring(8)}`;

				addVersionsToTitle(titleID, versions);
			}
		}
	}
}

async function scrapeYellows8() {
	let response = await axios.get('https://yls8.mtheall.com/ninupdates/eshop/verlist_parser.php');
	let $ = cheerio.load(response.data);
	const anchors = $('table#table tbody tr td a');
	const links = anchors.toArray().map(anchor => `https://yls8.mtheall.com/ninupdates/eshop/verlist_parser.php${anchor.attribs.href}`);

	for (const link of links) {
		response = await axios.get(link);
		$ = cheerio.load(response.data);
		const tableDatas = $('td');

		// * Page is structured as a table of rows which 2 td's each
		for (let i = 0; i < tableDatas.length; i+=2) {
			let titleID = $(tableDatas[i]).text();
			const version = $(tableDatas[i+1]).text();

			addVersionsToTitle(titleID, [version]);

			// * Catch any versions assigned to updates or DLC which aren't assinged to the base title
			if (titleID.startsWith('0004000E') || titleID.startsWith('0004000C')) {
				titleID = `00040000${titleID.substring(8)}`;

				addVersionsToTitle(titleID, [version]);
			}
		}
	}
}


async function scrapeTagayaWUP() {
	const httpsAgent = new https.Agent({
		rejectUnauthorized: false,
		cert: fs.readFileSync('./certs/wiiu-common.crt'),
		key: fs.readFileSync('./certs/wiiu-common.key'),
	});

	// * Despite taking in a region and country, this server seems to
	// * ignore both and send the same data no matter what. Just use
	// * USA/US for now
	let response = await axios.get('https://tagaya-wup.cdn.nintendo.net/tagaya/versionlist/USA/US/latest_version', {
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});
	const data = xmlParser(response.data).toObject();
	const latestVersion = Number(data.version_list_info.version);

	for (let i = 1; i < latestVersion; i++) {
		response = await axios.get(`https://tagaya-wup.cdn.nintendo.net/tagaya/versionlist/USA/US/list/${i}.versionlist`, {
			validateStatus: () => {
				return true;
			},
			httpsAgent
		});

		const xml = xmlParser(response.data).toObject();

		if (!xml.version_list) {
			continue;
		}

		let versionList = xml.version_list.titles.title;

		if (!versionList) {
			continue;
		}

		if (!Array.isArray(versionList)) {
			// * Only one item in the version list
			versionList = [versionList];
		}

		for (const title of versionList) {
			let titleID = title.id.replace('-', '').toUpperCase();
			const versions = [title.version];

			addVersionsToTitle(titleID, versions);

			// * Catch any versions assigned to updates or DLC which aren't assinged to the base title
			if (titleID.startsWith('0005000E') || titleID.startsWith('0005000C')) {
				titleID = `00050000${titleID.substring(8)}`;

				addVersionsToTitle(titleID, versions);
			}
		}
	}
}

async function scrapeTagayaCTR() {
	const httpsAgent = new https.Agent({
		rejectUnauthorized: false,
		cert: fs.readFileSync('./certs/wiiu-common.crt'),
		key: fs.readFileSync('./certs/wiiu-common.key'),
	});

	// * This server has no way of getting old title versions
	const response = await axios.get('https://tagaya-ctr.cdn.nintendo.net/tagaya/versionlist', {
		responseType: 'arraybuffer',
		validateStatus: () => {
			return true;
		},
		httpsAgent
	});

	const versionList = response.data;

	for (let i = 0; i < versionList.length; i+=0x10) {
		let titleID = versionList.readBigUInt64LE(i).toString(16).padStart('16', 0).toUpperCase();
		const version = versionList.readUInt32LE(i+8);

		addVersionsToTitle(titleID, [version]);

		// * Catch any versions assigned to updates or DLC which aren't assinged to the base title
		if (titleID.startsWith('0004000E') || titleID.startsWith('0004000C')) {
			titleID = `00040000${titleID.substring(8)}`;

			addVersionsToTitle(titleID, [version]);
		}
	}
}

async function main() {
	await scrapeWiiUBrew();  // * Initial Wii U versions which may be missing from Tagaya
	await scrapeYellows8();  // * Contains 3DS version info going back as far as 2015. Thank you yellows, sorry for scraping you :(
	await scrapeTagayaWUP(); // * Anything not on wiiubrew
	await scrapeTagayaCTR(); // * Latest 3DS version list (does not contain legacy version lists)

	fs.writeFileSync('./title-versions.json', JSON.stringify(titles));
}


main();