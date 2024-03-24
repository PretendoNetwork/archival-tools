const axios = require('axios');
const fs = require('fs-extra');
const N64 = require('./nus.json'); // * Data from https://niwanetwork.org/wiki/List_of_Nintendo_64_games_by_serial_code
const DS = require('./ntr.json');  // * Data from http://sergio.silvestre.free.fr/KDO/DS/Jeux_NDS_20110103_VG.xlsm
const Wii = require('./rvl.json'); // * Data from https://www.gametdb.com/Wii/Downloads

const REGIONS = [
	'JPN', 'USA', 'EUR',
	'CHN', 'KOR', 'TWN'
];

const LANGUAGES = [
	'J', // * Japanese
	'E', // * English
	'F', // * French
	'G', // * German
	'I', // * Italian
	'S', // * Spanish
	'K', // * Korean
	'D', // * Dutch
	'P', // * Portuguese
	'R', // * Russian
	'T'  // * Traditional
];

async function main() {
	// TODO - Can't seem to find manuals for NES, SNES, GBA, PC Engine, or TurboGrafx VC titles? What are the code names and product codes?
	await scrapeSystem('NUS', N64);
	await scrapeSystem('NTR', DS);
	await scrapeSystem('RVL', Wii);
}

async function scrapeSystem(codeName, productCodes) {
	for (const productCode of productCodes) {
		for (const region of REGIONS) {
			for (const language of LANGUAGES) {
				const response = await axios.get(`https://m1.nintendo.net/docvc/${codeName}/${region}/${productCode}/${productCode}_${language}.pdf`, {
					responseType: 'arraybuffer',
					validateStatus: () => {
						return true;
					}
				});

				if (response.status !== 200) {
					continue;
				}

				fs.ensureDirSync(`./manuals/${codeName}/${productCode}`);
				fs.writeFileSync(`./manuals/${codeName}/${productCode}/${productCode}-${region}_${language}.pdf`, response.data);
			}
		}
	}
}

main();