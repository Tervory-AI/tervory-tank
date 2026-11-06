const fs = require('node:fs');
const args = process.argv.slice(2);
const url = new URL(args.at(-1));
const dest = args[args.indexOf('-o') + 1];
const origin = new URL(process.env.TERVORY_TEST_RELEASE_ORIGIN);
if (origin.protocol !== 'http:' || origin.hostname !== '127.0.0.1' || !['opli.tervory.com', 'app.tervory.com'].includes(url.hostname)) process.exit(2);
fetch(new URL(url.pathname, origin)).then(async response => {
  if (!response.ok) process.exit(3);
  fs.writeFileSync(dest, Buffer.from(await response.arrayBuffer()));
}).catch(() => process.exit(4));
