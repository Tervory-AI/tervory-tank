import { closeSync, fsyncSync, mkdirSync, openSync, readFileSync, writeSync } from "node:fs";
import { dirname } from "node:path";

const EMAIL =
  /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

export function normalizeEmail(value) {
  if (typeof value !== "string") return null;
  const email = value.trim();
  if (email.length < 6 || email.length > 254) return null;
  if (/[\u0000-\u001F\u007F]/.test(email)) return null;
  if (!EMAIL.test(email)) return null;
  return email;
}

function fileContains(file, email) {
  let text = "";
  try {
    text = readFileSync(file, "utf8");
  } catch {
    return false;
  }
  for (const row of text.split("\n")) {
    if (!row) continue;
    try {
      if (JSON.parse(row).email === email) return true;
    } catch {
      // A torn line is not a stored address.
    }
  }
  return false;
}

function storeAddressSync(file, email) {
  const clean = normalizeEmail(email);
  if (!clean) return { status: 400, stored: false };
  try {
    mkdirSync(dirname(file), { recursive: true });
    const line = `${JSON.stringify({ email: clean, at: new Date().toISOString() })}\n`;
    const fd = openSync(file, "a");
    try {
      writeSync(fd, line);
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
  } catch {
    return { status: 500, stored: false };
  }
  if (!fileContains(file, clean)) return { status: 500, stored: false };
  return { status: 200, stored: true };
}

let chain = Promise.resolve();

export function storeAddress(file, email) {
  const run = chain.then(() => storeAddressSync(file, email));
  chain = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}
