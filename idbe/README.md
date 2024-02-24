# IDBE
## Download all known IDBE icons

## IDBE Files
IDBE files contain icon graphics and metadata for a title. These are used in titles like Download Management on the Wii U, and the friends server on both platforms, to show a titles icon if it's not already installed locally. See https://nintendo-wiki.pretendo.network/docs/idbe for documentation on the files structure

## Usage
- Install [NodeJS](https://nodejs.org)
- `npm i`
- `node get_versions.js` (Only if `title-versions.json` needs to be created/updated)
- `node scrape.js`

## Downloads
Files are downloaded into the `icons` directory. Each subfolder name is the titles title ID. Inside each folder will be at least one file, `latest.idbe`. This is the icon for the latest version of the title. Optionally there may be any number of other `.idbe` files, whose name is a previous version of the title. The highest number version is identical to `latest.idbe`.

## Title versions
The IDBE server stores icons for both current and past releases of all titles. In order to get past releases, a titles previous version numbers must be known. These versions are scraped from various sources:

- https://wiiubrew.org/wiki/Title_database - Contains lots of Wii U title versions not found in Tagaya.
- https://yls8.mtheall.com/ninupdates/eshop/verlist_parser.php - The only known place to get previous 3DS title versions.
- [Tagaya](https://nintendo-wiki.pretendo.network/docs/tagaya) (Wii U) - The Wii U Tagaya server contains all past version lists, which populate any missing versions from wiiubrew.
- [Tagaya](https://nintendo-wiki.pretendo.network/docs/tagaya) (3DS) - The 3DS Tagaya server only contains a version list of the most recent title versions. This is why Yellows8's site is used.

Yellows8's site only goes back to 2015, 4 years after the 3DS's launch. Due to this, there is 4 years worth of 3DS title versions missing from this archive unless another source is found which contains them.