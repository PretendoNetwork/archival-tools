const sqlite = require('sqlite');
const sqlite3 = require('sqlite3');

let database;

async function connect() {
	database = await sqlite.open({
		filename: 'tasks.db',
		driver: sqlite3.Database
	});
}

function verifyConnected() {
	if (!database) {
		throw new Error('Tried to interact with unopened database');
	}
}

function all(query, ...arguments) {
	verifyConnected();

	return database.all(query, arguments);
}

function exec(query) {
	verifyConnected();

	return database.exec(query);
}

function run(query, ...arguments) {
	verifyConnected();

	return database.run(query, arguments);
}

function getNextBatch(platform, size=50) {
	return all('SELECT * FROM tasks WHERE platform = ? AND processed = FALSE LIMIT ?', platform, size);
}

function rowProcessed(id) {
	return run('UPDATE tasks SET processed = TRUE WHERE id = ?', id);
}

function close() {
	verifyConnected();

	return database.close();
}

module.exports = {
	connect,
	all,
	exec,
	run,
	getNextBatch,
	rowProcessed,
	close
};