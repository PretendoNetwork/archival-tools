# SpotPass (BOSS)
## Download all known SpotPass/BOSS content

# Usage
- Install NodeJS
- Add any missing BOSS tasks to `ctr-boss-apps.json` (3DS) and/or `wup-boss-apps.json` (Wii U)
- `npm i`
- Create the tasks [database](#database)
- `node scrape`

# Database
This scraper relies on a database of BOSS tasks to archive. This is done so archiving may be done batches rather than all at once. The SQLite schema looks as follows

```sql
CREATE TABLE IF NOT EXISTS tasks (
	id        INTEGER PRIMARY KEY,
	platform  TEXT,
	app_id    TEXT,
	task      TEXT,
	country   TEXT,
	language  TEXT,
	processed BOOLEAN
)
```

The archiver pulls unprocessed rows in batches and processes them concurrently. This way the archiver may be stopped and started without losing progress and redownloading existing content. This is useful for batch archiving or in the event that the tool crashes.

To build the database:

- Ensure both `ctr-boss-apps.json` (3DS) and `wup-boss-apps.json` (Wii U) contain all BOSS tasks to be archived
- `node build-database`

This creates a row for every task, in every app, for every possible country and region combination. The database will be somewhat large and take some time to build, as each task needs 1,157 rows.

# SpotPass/BOSS content
SpotPass, aka BOSS, content is region specific data used by titles for title-specific tasks. There is nearly no overlap in BOSS files content between games. Because of this, each game must have all it's regions checked manually.

# Tasks
Each title has a BOSS application ID associated with it. Each BOSS application can register a number of tasks, and these tasks download the content/files. For example, Super Mario Maker uses the application ID `vGwChBW1ExOoHDsm` for the US region. This application uses a task named `CHARA`, which downloads the costumes used in game.

There is no simple way to know a games BOSS application ID and associated tasks without checking your network traffic. See https://pretendo.network/docs/network-dumps#spotpass for more information on how to dump your traffic. This repository contains JSON lists of known applications and tasks, but this is far from complete.

# Downloads
Content is downloaded into the `data` folder. Since BOSS content may update over time, each run of the scraper is placed into it's own folder inside `data` with the name being the current date in `YYYY-MM-DD` format. Since BOSS content is region specific the following subdirectories are the country and language code. Finally, each BOSS application has it's own folder which has additional folders for each task. These folders contain the `.boss` content files, as well as a `filelist.txt` (3DS) or `tasksheet.xml` (Wii U) file depending on the console.

An example download path would be `data/2024-01-27/GB/en/0hFlOFo7pNTU2dyE/RNG_EC1` which holds the GB-en region content for BOSS task `RNG_EC1` in application `0hFlOFo7pNTU2dyE`.

Downloads brute-force the regions, these will take a while to finish downloading. This will create lots of duplicate data, resulting in very large archive sizes.