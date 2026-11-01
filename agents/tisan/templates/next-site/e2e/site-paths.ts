import { createRequire } from "node:module";

const paths = createRequire(import.meta.url)("../scripts/site-paths.cjs") as {
  sitePaths: () => string[];
};
export const sitePaths = paths.sitePaths;
