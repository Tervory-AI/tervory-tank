const fs = require("node:fs");
if (!fs.existsSync("visual/frames.json")) {
  console.error("frame data incomplete");
  process.exit(1);
}
