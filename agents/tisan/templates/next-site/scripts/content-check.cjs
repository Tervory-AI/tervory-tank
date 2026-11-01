const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const manifest = require("../sections/manifest.json");
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

// Enforce the draft 2020-12 subset used by the shared manifest. Refuse new
// keywords until they have an implementation rather than silently ignoring them.
function validateSchema(value, schema, path, errors) {
  const supported = new Set([
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "pattern",
    "enum",
  ]);
  for (const key of Object.keys(schema)) {
    if (!supported.has(key)) errors.push(`${path}: unsupported schema keyword ${key}`);
  }
  if (schema.enum && !schema.enum.includes(value)) errors.push(`${path}: invalid enum value`);
  const matches = {
    object: object(value),
    array: Array.isArray(value),
    string: typeof value === "string",
  };
  if (schema.type && !matches[schema.type]) {
    errors.push(`${path}: expected ${schema.type}`);
    if (schema.type !== "object") return;
    value = {};
  }
  if (schema.type === "object") {
    const props = schema.properties || {};
    for (const key of schema.required || []) {
      if (!own(value, key)) {
        errors.push(`${path}/${key}: missing required value`);
        // Also list missing image src/alt and other required descendants.
        if (props[key]?.type === "object") validateSchema({}, props[key], `${path}/${key}`, errors);
      }
    }
    for (const key of Object.keys(value)) {
      if (own(props, key)) validateSchema(value[key], props[key], `${path}/${key}`, errors);
      else if (schema.additionalProperties === false)
        errors.push(`${path}/${key}: unknown property`);
    }
  }
  if (schema.type === "array") {
    if (value.length < (schema.minItems || 0)) errors.push(`${path}: too few items`);
    if (schema.maxItems !== undefined && value.length > schema.maxItems)
      errors.push(`${path}: too many items`);
    value.forEach((item, index) => validateSchema(item, schema.items, `${path}/${index}`, errors));
  }
  if (schema.type === "string") {
    const length = [...value].length;
    if (schema.minLength && (!value.trim() || length < schema.minLength))
      errors.push(`${path}: missing or empty text/image value`);
    if (schema.maxLength !== undefined && length > schema.maxLength)
      errors.push(`${path}: too long`);
    if (schema.pattern && !new RegExp(schema.pattern).test(value))
      errors.push(`${path}: invalid format`);
  }
}

const text = { type: "string", minLength: 1 };
const documentSchema = {
  type: "object",
  additionalProperties: false,
  required: ["schema", ...manifest.site.props.required, "pages"],
  properties: {
    schema: { enum: ["tisan.content/1"] },
    ...manifest.site.props.properties,
    pages: {
      type: "array",
      minItems: 1,
      items: {
        type: "object",
        additionalProperties: false,
        required: ["name", "path", "title", "sections"],
        properties: {
          name: { ...text, pattern: "^[a-z0-9-]{1,40}$" },
          path: { ...text, pattern: "^/(?:[a-z0-9-]+(?:/[a-z0-9-]+)*)?$" },
          title: text,
          sections: {
            type: "array",
            items: {
              type: "object",
              additionalProperties: false,
              required: ["type", "id", "props"],
              properties: {
                type: text,
                id: { ...text, pattern: "^[a-z0-9-]{1,40}$" },
                props: { type: "object" },
              },
            },
          },
        },
      },
    },
  },
};

function checkContent(content) {
  const errors = [];
  validateSchema(content, documentSchema, "site", errors);
  const names = new Set(),
    paths = new Set();
  if (Array.isArray(content?.pages))
    content.pages.forEach((page, index) => {
      if (!object(page)) return;
      const prefix = `site/pages/${index}`;
      for (const [key, seen] of [
        ["name", names],
        ["path", paths],
      ]) {
        if (seen.has(page[key])) errors.push(`${prefix}/${key}: duplicate value`);
        seen.add(page[key]);
      }
      if (["/contact", "/privacy"].includes(page.path) || /^\/(api|_next)(\/|$)/.test(page.path))
        errors.push(`${prefix}/path: reserved route`);
      const ids = new Set();
      if (Array.isArray(page.sections))
        page.sections.forEach((section, sectionIndex) => {
          if (!object(section)) return;
          const location = `${prefix}/sections/${sectionIndex}`;
          if (ids.has(section.id)) errors.push(`${location}/id: duplicate value`);
          ids.add(section.id);
          if (!own(manifest.sections, section.type))
            errors.push(`${location}/type: unknown section type ${section.type}`);
          else
            validateSchema(
              section.props,
              manifest.sections[section.type].props,
              `${location}/props`,
              errors,
            );
        });
    });
  return errors;
}

function loadContent(root = process.cwd()) {
  let raw;
  try {
    raw = readFileSync(join(root, "content/site.json"), "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
  const content = JSON.parse(raw);
  const errors = checkContent(content);
  if (errors.length) throw new Error(errors.join("\n"));
  return content;
}
if (require.main === module) {
  try {
    loadContent();
    console.log("Content check passed");
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
module.exports = { checkContent, loadContent, validateSchema };
