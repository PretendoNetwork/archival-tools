function millisecondsToString(ms) {
	const seconds = Math.floor((ms / 1000) % 60);
	const minutes = Math.floor((ms / 1000 / 60) % 60);
	const hours = Math.floor((ms  / 1000 / 3600 ) % 24)

	return [
		`${hours.toString().padStart(2, '0')}h`,
		`${minutes.toString().padStart(2, '0')}m`,
		`${seconds.toString().padStart(2, '0')}s`
	].join(':');
}

module.exports = {
	millisecondsToString
};