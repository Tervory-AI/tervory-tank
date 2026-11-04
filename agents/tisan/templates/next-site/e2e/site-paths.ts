import { createRequire } from "node:module";
import { join } from "node:path";

const paths = createRequire(join(process.cwd(), "package.json"))("./scripts/site-paths.cjs") as {
  sitePaths: () => string[];
};
export const sitePaths = paths.sitePaths;
