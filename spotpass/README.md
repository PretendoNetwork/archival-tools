# SpotPass (BOSS)
## Download all known SpotPass/BOSS content

# Usage
- Install NodeJS v18 or newer. If you're on Ubuntu or something and running an ancient version of node that comes with it by default (run `node -v` to see what version you have), figure it out and get the new one.
- Add any missing BOSS tasks to `ctr-boss-apps.json` (3DS) and/or `wup-boss-apps.json` (Wii U)
- `npm i` to install dependencies.
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
SpotPass, aka BOSS, content is region specific data used by titles for title-specific tasks. There is nearly no overlap in BOSS files content between games. Because of this, each game must have all its regions checked manually.

# Tasks
Each title has a BOSS application ID associated with it. Each BOSS application can register a number of tasks, and these tasks download the content/files. For example, Super Mario Maker uses the application ID `vGwChBW1ExOoHDsm` for the US region. This application uses a task named `CHARA`, which downloads the costumes used in game.

There is no simple way to know a games BOSS application ID and associated tasks without checking your network traffic. See https://pretendo.network/docs/network-dumps#spotpass for more information on how to dump your traffic. This repository contains JSON lists of known applications and tasks, but this is far from complete.

# Console databases
Both consoles have databases for storing lists of BOSS tasks. These can be used to build the JSON files by using either `read-boss-db-wiiu.js` or `read-boss-db-3ds.js` depending on your console.

A BOSS task must be registered in order to appear in the database. Typically a game will register all of it's tasks once SpotPass is enabled for the game. A game may require the user to be online before asking to enable SpotPass, but this depends on the game.

### Wii U BOSS database
The Wii U stores a separate database of BOSS tasks per user. Each one must be dumped individually.

- Connect to the Wii U using FTP
- Navigate to `/storage_mlc/usr/save/system/boss`
- Find the folder for the user you want to dump the database for
- Dump the `task.db` file
- Place the `task.db` file here and run `node read-boss-db-wiiu`

### 3DS BOSS database
The 3DS stores BOSS tasks in a single save file in the BOSS sysmodule.

- Launch GodMode9
- Navigate to `SYSNAND CTRNAND > data > longstring > sysdata > 00010034`
- Open `00000000`. If your file is not named `00000000` you may still continue, though we cannot guarantee this is the correct file. If you have more than one file, repeat the following steps for each
- Select `Mount as DISA image`
- Press `A` to mount and enter the image
- Select `PartitionA.bin`. If your file is not named `PartitionA.bin` you may still continue, though we cannot guarantee this is the correct file. If you have more than one file, repeat the following steps for each
- Select `Copy to 0:/gm9/out`
- Turn off your console and eject the SD card
- Open your SD card on your computer and place the `sd:/gm9/out/PartitionA.bin` file here
- Run `node read-boss-db-3ds`

# Downloads
Content is downloaded into the `data` folder. Since BOSS content may update over time, each run of the scraper is placed into it's own folder inside `data` with the name being the current date in `YYYY-MM-DD` format. Since BOSS content is region specific the following subdirectories are the country and language code. Finally, each BOSS application has it's own folder which has additional folders for each task. These folders contain the `.boss` content files, as well as a `filelist.txt` (3DS) or `tasksheet.xml` (Wii U) file depending on the console. Content files will also be accompanied by a `headers.txt` containing additional data such as modification timestamp.

An example download path would be `data/2024-01-27/GB/en/0hFlOFo7pNTU2dyE/RNG_EC1` which holds the GB-en region content for BOSS task `RNG_EC1` in application `0hFlOFo7pNTU2dyE`.

Downloads brute-force the regions, these will take a while to finish downloading. This will create lots of duplicate data, resulting in very large archive sizes.
