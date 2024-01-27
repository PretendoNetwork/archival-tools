# SpotPass (BOSS)
## Download all known SpotPass/BOSS content

# Usage
- Install NodeJS
- Add any missing BOSS tasks to `ctr-boss-apps.json` (3DS) and/or `wup-boss-apps.json` (Wii U)
- `npm i`
- `node scrape`

# SpotPass/BOSS content
SpotPass, aka BOSS, content is region specific data used by titles for title-specific tasks. There is nearly no overlap in BOSS files content between games. Because of this, each game must have all it's regions checked manually.

# Tasks
Each title has a BOSS application ID associated with it. Each BOSS application can register a number of tasks, and these tasks download the content/files. For example, Super Mario Maker uses the application ID `vGwChBW1ExOoHDsm` for the US region. This application uses a task named `CHARA`, which downloads the costumes used in game.

There is no simple way to know a games BOSS application ID and associated tasks without checking your network traffic. See https://pretendo.network/docs/network-dumps#spotpass for more information on how to dump your traffic. This repository contains JSON lists of known applications and tasks, but this is far from complete.

# Downloads
Content is downloaded into the `data` folder. Since BOSS content may update over time, each run of the scraper is placed into it's own folder inside `data` with the name being the current date in `YYYY-MM-DD` format. Since BOSS content is region specific the following subdirectories are the country and language code. Finally, each BOSS application has it's own folder which has additional folders for each task. These folders contain the `.boss` content files, as well as a `filelist.txt` (3DS) or `tasksheet.xml` (Wii U) file depending on the console.

An example download path would be `data/2024-01-27/GB/en/0hFlOFo7pNTU2dyE/RNG_EC1` which holds the GB-en region content for BOSS task `RNG_EC1` in application `0hFlOFo7pNTU2dyE`.

Downloads brute-force the regions, these will take a while to finish downloading. This will create lots of duplicate data, resulting in very large archive sizes.