import { readFileSync } from "node:fs";
import { caseRecord } from "../workspace/app/skala/record.ts";

const payload = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(caseRecord(payload)));
