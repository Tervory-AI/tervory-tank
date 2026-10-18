const data = window.RIG_BUILD || { centres: [], products: [], fits: [], assets: {}, measured: "not checked" };
const centreSelect = document.querySelector("#centre");
const centreName = document.querySelector("#centre-name");
const centreMeta = document.querySelector("#centre-meta");
const centrePrice = document.querySelector("#centre-price");
const centreFile = document.querySelector("#centre-file");
const fitCount = document.querySelector("#fit-count");
const groups = document.querySelector("#groups");
const lines = document.querySelector("#lines");
const quoteNote = document.querySelector("#quote-note");
const total = document.querySelector("#total");
const emptyCopy = document.querySelector("#empty-copy");
const skuList = document.querySelector("#sku-list");
const stage = document.querySelector("#stage");
const canvas = document.querySelector("#view");
const viewStatus = document.querySelector("#view-status");
const sendStatus = document.querySelector("#send-status");
const turnButton = document.querySelector("#turn");
const closeButton = document.querySelector("#closeup");

const selected = new Set();
let spinning = false;
let closeUp = false;
let focusSku = "";
let viewer = null;

const params = new URLSearchParams(window.location.search);
for (const sku of (params.get("parts") || "").split(",")) {
  if (sku) selected.add(sku);
}

centreSelect.addEventListener("change", () => {
  selected.clear();
  focusSku = "";
  const next = "/build/" + encodeURIComponent(centreSelect.value);
  history.pushState({}, "", next);
  draw();
});

window.addEventListener("popstate", draw);

turnButton.addEventListener("click", () => {
  if (!placedCount()) {
    viewStatus.textContent = "Nothing to turn yet. Size against the real product has not been checked.";
    return;
  }
  spinning = !spinning;
  turnButton.setAttribute("aria-pressed", spinning ? "true" : "false");
  viewStatus.textContent = spinning
    ? "Turning. Size against the real product has not been checked."
    : "Size against the real product has not been checked.";
});

closeButton.addEventListener("click", () => {
  if (!placedCount()) {
    viewStatus.textContent = "Nothing to move in on. Size against the real product has not been checked.";
    return;
  }
  closeUp = !closeUp;
  closeButton.setAttribute("aria-pressed", closeUp ? "true" : "false");
});

document.querySelector("#picture").addEventListener("click", () => {
  if (!placedCount() || !viewer) {
    viewStatus.textContent = "There is no picture yet. Size against the real product has not been checked.";
    return;
  }
  const link = document.createElement("a");
  link.href = canvas.toDataURL("image/png");
  link.download = "build.png";
  link.click();
});

document.querySelector("#share").addEventListener("click", async () => {
  const url = new URL(window.location.href);
  url.pathname = "/build/" + encodeURIComponent(currentId());
  if (selected.size) url.searchParams.set("parts", [...selected].join(","));
  else url.searchParams.delete("parts");
  try {
    await navigator.clipboard.writeText(url.toString());
    sendStatus.textContent = "Link copied.";
  } catch {
    sendStatus.textContent = url.toString();
  }
});

document.querySelector("#send").addEventListener("submit", (event) => {
  event.preventDefault();
  void sendBuild();
});

function draw() {
  const centre = currentCentre();
  fillCentres(centre);
  if (!centre) {
    centreName.textContent = "No such product.";
    groups.replaceChildren();
    lines.replaceChildren();
    return;
  }
  centreName.textContent = centre.name || "";
  centreMeta.textContent = [centre.brand, centre.category].filter(Boolean).join(" · ");
  centrePrice.textContent = priceLine(centre.price);
  const asset = (data.assets || {})[idOf(centre)] || {};
  centreFile.hidden = !!asset.present;
  const parts = partsThatFit(centre);
  for (const sku of [...selected]) {
    if (!parts.some((part) => idOf(part) === sku)) selected.delete(sku);
  }
  fitCount.textContent = fitSentence(parts);
  renderGroups(parts);
  const scene = assemble(centre, parts.filter((part) => selected.has(idOf(part))));
  renderQuote(scene);
  renderStage(centre, parts, scene);
  if (viewer) viewer.show(scene.lines.filter((line) => line.placed));
}

function fillCentres(centre) {
  const centres = data.centres && data.centres.length ? data.centres : data.products || [];
  const current = centreSelect.value;
  centreSelect.replaceChildren();
  for (const row of centres) {
    const option = document.createElement("option");
    option.value = idOf(row);
    option.textContent = row.name || idOf(row);
    centreSelect.append(option);
  }
  const wanted = centre ? idOf(centre) : current;
  if ([...centreSelect.options].some((option) => option.value === wanted)) centreSelect.value = wanted;
}

function currentId() {
  const match = window.location.pathname.match(/^\/build\/([^/]+)$/);
  if (match) return decodeURIComponent(match[1]);
  const centres = data.centres || [];
  return centres.length ? idOf(centres[0]) : "";
}

function currentCentre() {
  const wanted = currentId();
  const rows = data.products || [];
  return rows.find((row) => idOf(row) === wanted) || (data.centres || [])[0] || null;
}

function renderGroups(parts) {
  groups.replaceChildren();
  const buckets = new Map();
  for (const part of parts) {
    const name = part.category || "Parts";
    if (!buckets.has(name)) buckets.set(name, []);
    buckets.get(name).push(part);
  }
  for (const [name, rows] of buckets) {
    const block = document.createElement("div");
    block.className = "group";
    const heading = document.createElement("h3");
    heading.textContent = name;
    block.append(heading);
    for (const part of rows) block.append(partButton(part));
    groups.append(block);
  }
}

function partButton(part) {
  const sku = idOf(part);
  const asset = (data.assets || {})[sku] || {};
  const button = document.createElement("button");
  button.type = "button";
  button.className = "part";
  button.setAttribute("aria-pressed", selected.has(sku) ? "true" : "false");
  const title = document.createElement("strong");
  title.textContent = part.name || sku;
  const meta = document.createElement("span");
  meta.className = "split";
  const price = document.createElement("span");
  price.className = "price";
  price.textContent = priceLine(part.price);
  meta.append(price);
  if (!asset.present) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = "Model file needed";
    meta.append(chip);
  }
  button.append(title, meta);
  button.addEventListener("click", () => {
    if (selected.has(sku)) selected.delete(sku);
    else {
      selected.add(sku);
      focusSku = sku;
    }
    draw();
  });
  return button;
}

function renderQuote(scene) {
  lines.replaceChildren();
  for (const line of scene.lines) {
    const item = document.createElement("li");
    const name = document.createElement("div");
    name.textContent = line.name;
    const price = document.createElement("div");
    price.className = "price";
    price.textContent = priceLine(line.price);
    item.append(name, price);
    if (line.reason) {
      const reason = document.createElement("p");
      reason.className = "reason";
      reason.textContent = line.reason;
      item.append(reason);
    } else if (line.collision && line.collision !== "checked") {
      const reason = document.createElement("p");
      reason.className = "reason";
      reason.textContent = line.collision;
      item.append(reason);
    }
    lines.append(item);
  }
  const drawn = scene.lines.filter((line) => line.role !== "host" && line.placed).length;
  const waiting = scene.lines.filter((line) => line.reason === "needs a model file").length;
  if (waiting) {
    quoteNote.textContent = "A part is drawn only when its model file is in the catalogue, and it sits on the mount that file names.";
  } else if (!drawn) {
    quoteNote.textContent = "No other part is placed.";
  } else {
    quoteNote.textContent = "Placed on the mounts named in the model files.";
  }
  total.textContent = priceLine(scene.total);
}

function renderStage(centre, parts, scene) {
  const missing = [];
  const centreAsset = (data.assets || {})[idOf(centre)] || {};
  if (!centreAsset.present) missing.push(idOf(centre));
  for (const part of parts) {
    const asset = (data.assets || {})[idOf(part)] || {};
    if (!asset.present) missing.push(idOf(part));
  }
  const placed = scene.lines.some((line) => line.placed);
  stage.classList.toggle("has-model", placed);
  const file = centreAsset.file || "models/" + idOf(centre) + ".glb";
  emptyCopy.textContent = (centre.name || "This product") + " needs " + file + ". A missing file is left blank. Nothing is drawn in its place.";
  skuList.textContent = missing.join("  ");
}

function fitSentence(parts) {
  const count = parts.length;
  const noun = count === 1 ? "part fits" : "parts fit";
  const needing = parts.filter((part) => !((data.assets || {})[idOf(part)] || {}).present).length;
  if (!count) return "No parts are listed as fitting this product.";
  if (needing === count) return count + " " + noun + " this product. None of them have a model file.";
  if (needing) return count + " " + noun + " this product. " + needing + " still need a model file.";
  return count + " " + noun + " this product.";
}

function placedCount() {
  const centre = currentCentre();
  if (!centre) return 0;
  const parts = partsThatFit(centre).filter((part) => selected.has(idOf(part)));
  return assemble(centre, parts).lines.filter((line) => line.placed).length;
}

async function sendBuild() {
  const name = document.querySelector("#who").value.trim();
  const email = document.querySelector("#email").value.trim();
  sendStatus.textContent = "Sending…";
  let response;
  try {
    response = await fetch("/v1/rig/quote", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Rig-Key": window.RIG_KEY || "",
      },
      body: JSON.stringify({
        build: { product_id: currentId(), part_skus: [...selected] },
        contact: { name, email },
      }),
    });
  } catch {
    sendStatus.textContent = "The build was not sent. Try again.";
    return;
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    sendStatus.textContent = (body.error && body.error.message) || "The build was not sent.";
    return;
  }
  sendStatus.textContent = "Sent. Request " + (body.request_id || "") + ".";
}

function idOf(row) {
  return String((row && (row.id || row.sku)) || "");
}

function priceLine(price) {
  if (!price || price.amount == null) return "";
  const value = Number(price.amount);
  const amount = Number.isFinite(value)
    ? value.toLocaleString("en-ZA", { maximumFractionDigits: 2 })
    : String(price.amount);
  return price.currency ? amount + " " + price.currency : amount;
}

function roleFor(category) {
  const slug = String(category || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || "part";
}

function partsThatFit(centre) {
  const products = data.products || [];
  const order = new Map(products.map((row, index) => [idOf(row), index]));
  const found = [];
  const seen = new Set();
  for (const fit of data.fits || []) {
    if (!fitOk(fit) || !fitTargets(fit, centre) || !ruleOk(fit.rule, centre.attributes)) continue;
    const part = products.find((row) => idOf(row) === fit.part_sku);
    if (!part || idOf(part) === idOf(centre) || seen.has(idOf(part))) continue;
    if ((part.price && part.price.currency) !== (centre.price && centre.price.currency)) continue;
    seen.add(idOf(part));
    found.push(part);
  }
  found.sort((left, right) => (order.get(idOf(left)) || 0) - (order.get(idOf(right)) || 0));
  return found;
}

function fitOk(fit) {
  if (fit.source === "suggested") return !!fit.approved;
  return fit.approved !== false;
}

function fitTargets(fit, centre) {
  if (fit.fits_sku && fit.fits_sku === idOf(centre)) return true;
  return !!(fit.fits_family && fit.fits_family === (centre.family || ""));
}

function ruleOk(rule, attributes) {
  if (!rule || typeof rule !== "object") return true;
  const facts = attributes || {};
  for (const key of Object.keys(rule)) {
    const expected = rule[key];
    const actual = facts[key];
    if (Array.isArray(expected) && expected.length === 2 && expected.every((item) => typeof item === "number")) {
      if (typeof actual !== "number" || actual < expected[0] || actual > expected[1]) return false;
      continue;
    }
    if (actual !== expected) return false;
  }
  return true;
}

function assemble(centre, parts) {
  const assets = data.assets || {};
  const host = assets[idOf(centre)] || {};
  const sceneLines = [lineFor(centre, "host", host, !!host.present, host.present ? null : "needs a model file")];
  const used = new Set();
  const boxes = [];
  const hostBox = boxAt(identity(), host.clearance_mm, host.unit || "m");
  if (host.present && hostBox) boxes.push(hostBox);
  for (const part of parts) {
    sceneLines.push(placePart(part, host, assets[idOf(part)] || {}, used, boxes));
  }
  const currency = (centre.price && centre.price.currency) || "";
  const amount = sceneLines.reduce((sum, line) => sum + Number(line.price.amount || 0), 0);
  return {
    lines: sceneLines,
    total: { amount, currency, indicative: true },
    measured: "not checked",
  };
}

function placePart(part, host, asset, used, boxes) {
  const role = roleFor(part.category);
  if (!asset.present) return lineFor(part, role, asset, false, "needs a model file");
  if (!host.present) {
    return lineFor(part, role, asset, false, "The centre has no model file, so this part is not drawn.");
  }
  const mount = (host.mounts || []).find((item) => item.role === role && !used.has(item.name || role));
  if (!mount) return lineFor(part, role, asset, false, "No mount in the model for this part.");
  const matrix = snap(mount, asset.attach);
  const clearance = asset.clearance_mm || mount.clearance_mm;
  const box = clearance ? boxAt(matrix, clearance, host.unit || "m") : null;
  if (box && boxes.some((other) => overlaps(box, other))) {
    return lineFor(part, role, asset, false, "It overlaps a part already placed.");
  }
  if (box) boxes.push(box);
  used.add(mount.name || role);
  const line = lineFor(part, role, asset, true, null);
  line.mount = mount.name || role;
  line.matrix = matrix;
  line.collision = box ? "checked" : "No clearance box in the file, so overlap was not checked.";
  return line;
}

function lineFor(product, role, asset, placed, reason) {
  return {
    sku: idOf(product),
    name: product.name || "",
    role,
    price: product.price || { amount: 0, currency: "", indicative: true },
    placed,
    file: asset.file || null,
    mount: null,
    reason,
    matrix: identity(),
  };
}

function snap(mount, attach) {
  let matrix = (mount.matrix || identity()).slice();
  if (attach && attach.matrix) matrix = multiply(matrix, rigidInverse(attach.matrix));
  return matrix;
}

function boxAt(matrix, size, unit) {
  if (!Array.isArray(size) || size.length !== 3 || size.some((item) => !(item > 0))) return null;
  const scale = unit === "mm" ? 1 : 1000;
  const center = [matrix[12] * scale, matrix[13] * scale, matrix[14] * scale];
  const half = size.map((item) => item / 2);
  return [center.map((item, axis) => item - half[axis]), center.map((item, axis) => item + half[axis])];
}

function overlaps(left, right) {
  const gap = 0.05;
  return [0, 1, 2].every((axis) => left[0][axis] < right[1][axis] - gap && right[0][axis] < left[1][axis] - gap);
}

function identity() {
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
}

function multiply(left, right) {
  const out = new Array(16).fill(0);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      let sum = 0;
      for (let k = 0; k < 4; k += 1) sum += left[k * 4 + row] * right[column * 4 + k];
      out[column * 4 + row] = sum;
    }
  }
  return out;
}

function rigidInverse(matrix) {
  const inverse = [
    matrix[0], matrix[4], matrix[8], 0,
    matrix[1], matrix[5], matrix[9], 0,
    matrix[2], matrix[6], matrix[10], 0,
    0, 0, 0, 1,
  ];
  const tx = matrix[12];
  const ty = matrix[13];
  const tz = matrix[14];
  inverse[12] = -(inverse[0] * tx + inverse[4] * ty + inverse[8] * tz);
  inverse[13] = -(inverse[1] * tx + inverse[5] * ty + inverse[9] * tz);
  inverse[14] = -(inverse[2] * tx + inverse[6] * ty + inverse[10] * tz);
  return inverse;
}

function createViewer(target) {
  const gl = target.getContext("webgl2", { antialias: true, preserveDrawingBuffer: true, alpha: false });
  if (!gl) return null;
  const program = gl.createProgram();
  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT);
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.bindAttribLocation(program, 0, "a_pos");
  gl.bindAttribLocation(program, 1, "a_nrm");
  gl.bindAttribLocation(program, 2, "a_uv");
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
  gl.useProgram(program);
  gl.enable(gl.DEPTH_TEST);
  gl.enable(gl.CULL_FACE);
  const uniforms = {
    mvp: gl.getUniformLocation(program, "u_mvp"),
    model: gl.getUniformLocation(program, "u_model"),
    color: gl.getUniformLocation(program, "u_color"),
    metal: gl.getUniformLocation(program, "u_metal"),
    rough: gl.getUniformLocation(program, "u_rough"),
    eye: gl.getUniformLocation(program, "u_eye"),
    textured: gl.getUniformLocation(program, "u_textured"),
  };
  const cache = new Map();
  const shadow = shadowMesh(gl);
  let yaw = 0.6;
  let pitch = 0.35;
  let distance = 2;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let shown = [];

  target.addEventListener("pointerdown", (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    target.setPointerCapture(event.pointerId);
  });
  target.addEventListener("pointerup", () => {
    dragging = false;
  });
  target.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    yaw += (event.clientX - lastX) * 0.01;
    pitch = Math.max(-1.2, Math.min(1.2, pitch + (event.clientY - lastY) * 0.01));
    lastX = event.clientX;
    lastY = event.clientY;
  });

  function frame() {
    resize();
    if (spinning) yaw += 0.008;
    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
    gl.clearColor(0, 24 / 255, 64 / 255, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const bounds = sceneBounds(shown);
    const center = bounds ? midpoint(bounds.min, bounds.max) : [0, 0, 0];
    const radius = bounds ? Math.max(span(bounds), 0.05) : 1;
    const eyeDistance = (closeUp ? radius * 1.4 : radius * 2.8);
    distance = eyeDistance;
    const eye = orbit(center, yaw, pitch, distance);
    const view = lookAt(eye, closeUp && focusSku ? partCenter(shown, focusSku) || center : center, [0, 1, 0]);
    const projection = perspective(0.7, gl.drawingBufferWidth / Math.max(1, gl.drawingBufferHeight), 0.01, 100);
    const vp = multiply(projection, view);
    if (bounds) drawShadow(gl, program, uniforms, shadow, vp, bounds);
    for (const item of shown) {
      const parsed = cache.get(item.sku);
      if (!parsed) continue;
      for (const primitive of parsed.primitives) {
        const model = multiply(item.matrix || identity(), primitive.matrix);
        gl.uniformMatrix4fv(uniforms.model, false, model);
        gl.uniformMatrix4fv(uniforms.mvp, false, multiply(vp, model));
        gl.uniform3f(uniforms.color, primitive.color[0], primitive.color[1], primitive.color[2]);
        gl.uniform1f(uniforms.metal, primitive.metal);
        gl.uniform1f(uniforms.rough, primitive.rough);
        gl.uniform3f(uniforms.eye, eye[0], eye[1], eye[2]);
        gl.uniform1i(uniforms.textured, primitive.texture ? 1 : 0);
        if (primitive.texture) {
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, primitive.texture);
        }
        gl.bindVertexArray(primitive.vao);
        gl.drawElements(gl.TRIANGLES, primitive.count, primitive.indexType, 0);
      }
    }
    requestAnimationFrame(frame);
  }

  function resize() {
    const width = Math.max(1, target.clientWidth);
    const height = Math.max(1, target.clientHeight);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const nextW = Math.floor(width * ratio);
    const nextH = Math.floor(height * ratio);
    if (target.width !== nextW || target.height !== nextH) {
      target.width = nextW;
      target.height = nextH;
    }
  }

  requestAnimationFrame(frame);
  return {
    show(next) {
      shown = next;
      for (const item of next) {
        if (!cache.has(item.sku)) {
          cache.set(item.sku, null);
          void loadModel(item.sku).then((parsed) => cache.set(item.sku, parsed));
        }
      }
    },
  };

  async function loadModel(sku) {
    const response = await fetch("/models/" + encodeURIComponent(sku));
    if (!response.ok) return { primitives: [] };
    const parsed = await parseGlb(gl, await response.arrayBuffer());
    return parsed;
  }
}

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  return shader;
}

async function parseGlb(gl, buffer) {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  if (bytes.length < 20 || String.fromCharCode(...bytes.slice(0, 4)) !== "glTF") return { primitives: [] };
  let offset = 12;
  let json = null;
  let bin = new Uint8Array();
  while (offset + 8 <= bytes.length) {
    const length = view.getUint32(offset, true);
    const kind = view.getUint32(offset + 4, true);
    offset += 8;
    const chunk = bytes.slice(offset, offset + length);
    offset += length;
    if (kind === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(chunk));
    if (kind === 0x004e4942) bin = chunk;
  }
  if (!json) return { primitives: [] };
  const textures = await loadTextures(gl, json, bin);
  const worlds = worldMatrices(json.nodes || []);
  const primitives = [];
  (json.nodes || []).forEach((node, index) => {
    if (typeof node.mesh !== "number") return;
    const mesh = (json.meshes || [])[node.mesh];
    if (!mesh) return;
    for (const primitive of mesh.primitives || []) {
      const built = buildPrimitive(gl, json, bin, primitive, textures);
      if (!built) continue;
      built.matrix = worlds[index];
      primitives.push(built);
    }
  });
  return { primitives };
}

function buildPrimitive(gl, json, bin, primitive, textures) {
  const attributes = primitive.attributes || {};
  if (typeof attributes.POSITION !== "number") return null;
  const position = readAccessor(json, bin, attributes.POSITION);
  if (!position || position.component !== 5126) return null;
  let normal = typeof attributes.NORMAL === "number" ? readAccessor(json, bin, attributes.NORMAL) : null;
  if (!normal) normal = { data: flatNormals(position.data), component: 5126 };
  const uv = typeof attributes.TEXCOORD_0 === "number" ? readAccessor(json, bin, attributes.TEXCOORD_0) : null;
  const indices = typeof primitive.indices === "number" ? readAccessor(json, bin, primitive.indices) : null;
  if (!indices) return null;
  const material = (json.materials || [])[primitive.material] || {};
  const pbr = material.pbrMetallicRoughness || {};
  const factor = pbr.baseColorFactor || [0.7, 0.7, 0.72, 1];
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  bufferAttrib(gl, 0, position.data, 3);
  bufferAttrib(gl, 1, normal.data, 3);
  bufferAttrib(gl, 2, uv ? uv.data : new Float32Array(position.data.length / 3 * 2), uv ? 2 : 2);
  const indexBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
  const indexType = indices.component === 5125 ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT;
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, indices.component === 5125 ? indices.data : indices.data, gl.STATIC_DRAW);
  let texture = null;
  const texInfo = pbr.baseColorTexture;
  if (texInfo && textures[texInfo.index]) texture = textures[texInfo.index];
  return {
    vao,
    count: indices.count,
    indexType,
    matrix: identity(),
    color: factor,
    metal: typeof pbr.metallicFactor === "number" ? pbr.metallicFactor : 0,
    rough: typeof pbr.roughnessFactor === "number" ? pbr.roughnessFactor : 0.6,
    texture,
  };
}

function bufferAttrib(gl, location, data, size) {
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, data instanceof Float32Array ? data : new Float32Array(data), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(location);
  gl.vertexAttribPointer(location, size, gl.FLOAT, false, 0, 0);
}

function readAccessor(json, bin, index) {
  const accessor = (json.accessors || [])[index];
  const view = (json.bufferViews || [])[accessor.bufferView];
  if (!accessor || !view) return null;
  const start = (view.byteOffset || 0) + (accessor.byteOffset || 0);
  const count = accessor.count;
  const width = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }[accessor.type] || 1;
  const size = { 5123: 2, 5125: 4, 5126: 4 }[accessor.componentType];
  if (!size) return null;
  const stride = view.byteStride || width * size;
  if (accessor.componentType === 5126) {
    const out = new Float32Array(count * width);
    for (let i = 0; i < count; i += 1) {
      const copy = new Uint8Array(width * 4);
      copy.set(bin.subarray(start + i * stride, start + i * stride + width * 4));
      out.set(new Float32Array(copy.buffer), i * width);
    }
    return { data: out, count, component: 5126 };
  }
  if (accessor.componentType === 5123) {
    const out = new Uint16Array(count * width);
    const source = new DataView(bin.buffer, bin.byteOffset, bin.byteLength);
    for (let i = 0; i < count; i += 1) {
      for (let c = 0; c < width; c += 1) out[i * width + c] = source.getUint16(start + i * stride + c * 2, true);
    }
    return { data: out, count, component: 5123 };
  }
  if (accessor.componentType === 5125) {
    const out = new Uint32Array(count * width);
    const source = new DataView(bin.buffer, bin.byteOffset, bin.byteLength);
    for (let i = 0; i < count; i += 1) {
      for (let c = 0; c < width; c += 1) out[i * width + c] = source.getUint32(start + i * stride + c * 4, true);
    }
    return { data: out, count, component: 5125 };
  }
  return null;
}

async function loadTextures(gl, json, bin) {
  const images = [];
  for (const image of json.images || []) {
    if (typeof image.bufferView !== "number") {
      images.push(null);
      continue;
    }
    const view = json.bufferViews[image.bufferView];
    const start = view.byteOffset || 0;
    const bytes = bin.slice(start, start + view.byteLength);
    try {
      const bitmap = await createImageBitmap(new Blob([bytes], { type: image.mimeType || "image/png" }));
      const texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, bitmap);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      images.push(texture);
    } catch {
      images.push(null);
    }
  }
  const textures = [];
  for (const texture of json.textures || []) {
    textures.push(images[texture.source] || null);
  }
  return textures;
}

function flatNormals(positions) {
  const out = new Float32Array(positions.length);
  for (let i = 0; i + 8 < positions.length; i += 9) {
    const ax = positions[i + 3] - positions[i];
    const ay = positions[i + 4] - positions[i + 1];
    const az = positions[i + 5] - positions[i + 2];
    const bx = positions[i + 6] - positions[i];
    const by = positions[i + 7] - positions[i + 1];
    const bz = positions[i + 8] - positions[i + 2];
    let nx = ay * bz - az * by;
    let ny = az * bx - ax * bz;
    let nz = ax * by - ay * bx;
    const length = Math.hypot(nx, ny, nz) || 1;
    nx /= length;
    ny /= length;
    nz /= length;
    for (let k = 0; k < 3; k += 1) {
      out[i + k * 3] = nx;
      out[i + k * 3 + 1] = ny;
      out[i + k * 3 + 2] = nz;
    }
  }
  return out;
}

function worldMatrices(nodes) {
  const parents = new Map();
  nodes.forEach((node, index) => {
    for (const child of node.children || []) parents.set(child, index);
  });
  const cache = new Map();
  function world(index, trail) {
    if (cache.has(index)) return cache.get(index);
    if (trail.has(index) || !nodes[index]) return identity();
    const local = localMatrix(nodes[index]);
    const parent = parents.get(index);
    const result = parent == null ? local : multiply(world(parent, new Set(trail).add(index)), local);
    cache.set(index, result);
    return result;
  }
  return nodes.map((_, index) => world(index, new Set()));
}

function localMatrix(node) {
  if (Array.isArray(node.matrix) && node.matrix.length === 16) return node.matrix.map(Number);
  const t = node.translation || [0, 0, 0];
  const r = node.rotation || [0, 0, 0, 1];
  const s = node.scale || [1, 1, 1];
  const x = r[0];
  const y = r[1];
  const z = r[2];
  const w = r[3];
  const x2 = x + x;
  const y2 = y + y;
  const z2 = z + z;
  const xx = x * x2;
  const xy = x * y2;
  const xz = x * z2;
  const yy = y * y2;
  const yz = y * z2;
  const zz = z * z2;
  const wx = w * x2;
  const wy = w * y2;
  const wz = w * z2;
  return [
    (1 - (yy + zz)) * s[0], (xy + wz) * s[0], (xz - wy) * s[0], 0,
    (xy - wz) * s[1], (1 - (xx + zz)) * s[1], (yz + wx) * s[1], 0,
    (xz + wy) * s[2], (yz - wx) * s[2], (1 - (xx + yy)) * s[2], 0,
    t[0], t[1], t[2], 1,
  ];
}

function shadowMesh(gl) {
  const positions = [0, 0, 0];
  const segments = 24;
  for (let i = 0; i <= segments; i += 1) {
    const angle = (i / segments) * Math.PI * 2;
    positions.push(Math.cos(angle), 0, Math.sin(angle));
  }
  const data = new Float32Array(positions);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
  return { buffer, count: segments + 2 };
}

function drawShadow(gl, program, uniforms, shadow, vp, bounds) {
  const width = Math.max(bounds.max[0] - bounds.min[0], bounds.max[2] - bounds.min[2], 0.2);
  const model = [
    width, 0, 0, 0,
    0, 1, 0, 0,
    0, 0, width, 0,
    (bounds.min[0] + bounds.max[0]) / 2, bounds.min[1] - 0.001, (bounds.min[2] + bounds.max[2]) / 2, 1,
  ];
  gl.uniformMatrix4fv(uniforms.model, false, model);
  gl.uniformMatrix4fv(uniforms.mvp, false, multiply(vp, model));
  gl.uniform3f(uniforms.color, 0, 0, 0);
  gl.uniform1f(uniforms.metal, 0);
  gl.uniform1f(uniforms.rough, 1);
  gl.uniform1i(uniforms.textured, 0);
  gl.disableVertexAttribArray(1);
  gl.vertexAttrib3f(1, 0, 1, 0);
  gl.disableVertexAttribArray(2);
  gl.vertexAttrib2f(2, 0, 0);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  gl.bindBuffer(gl.ARRAY_BUFFER, shadow.buffer);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
  gl.drawArrays(gl.TRIANGLE_FAN, 0, shadow.count);
  gl.disable(gl.BLEND);
  void program;
}

function sceneBounds(items) {
  // The viewer frames whatever meshes have loaded. It does not invent a size.
  const parsed = items.filter((item) => item.matrix);
  if (!parsed.length) return null;
  let min = [Infinity, Infinity, Infinity];
  let max = [-Infinity, -Infinity, -Infinity];
  let any = false;
  for (const item of parsed) {
    const point = [item.matrix[12], item.matrix[13], item.matrix[14]];
    any = true;
    for (let axis = 0; axis < 3; axis += 1) {
      min[axis] = Math.min(min[axis], point[axis]);
      max[axis] = Math.max(max[axis], point[axis]);
    }
  }
  if (!any) return null;
  return { min, max };
}

function midpoint(min, max) {
  return [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
}

function span(bounds) {
  return Math.hypot(bounds.max[0] - bounds.min[0], bounds.max[1] - bounds.min[1], bounds.max[2] - bounds.min[2]);
}

function partCenter(items, sku) {
  const item = items.find((row) => row.sku === sku && row.matrix);
  if (!item) return null;
  return [item.matrix[12], item.matrix[13], item.matrix[14]];
}

function orbit(center, yaw, pitch, distance) {
  const cp = Math.cos(pitch);
  return [
    center[0] + distance * cp * Math.sin(yaw),
    center[1] + distance * Math.sin(pitch),
    center[2] + distance * cp * Math.cos(yaw),
  ];
}

function lookAt(eye, target, up) {
  const z = normalise([eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]]);
  const x = normalise(cross(up, z));
  const y = cross(z, x);
  return [
    x[0], x[1], x[2], 0,
    y[0], y[1], y[2], 0,
    z[0], z[1], z[2], 0,
    -(x[0] * eye[0] + x[1] * eye[1] + x[2] * eye[2]),
    -(y[0] * eye[0] + y[1] * eye[1] + y[2] * eye[2]),
    -(z[0] * eye[0] + z[1] * eye[1] + z[2] * eye[2]),
    1,
  ];
}

function perspective(fov, aspect, near, far) {
  const f = 1 / Math.tan(fov / 2);
  const nf = 1 / (near - far);
  return [
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) * nf, -1,
    0, 0, 2 * far * near * nf, 0,
  ];
}

function cross(a, b) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function normalise(v) {
  const length = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / length, v[1] / length, v[2] / length];
}

const VERTEX = `#version 300 es
layout(location=0) in vec3 a_pos;
layout(location=1) in vec3 a_nrm;
layout(location=2) in vec2 a_uv;
uniform mat4 u_mvp;
uniform mat4 u_model;
out vec3 v_pos;
out vec3 v_nrm;
out vec2 v_uv;
void main() {
  vec4 world = u_model * vec4(a_pos, 1.0);
  v_pos = world.xyz;
  v_nrm = mat3(u_model) * a_nrm;
  v_uv = a_uv;
  gl_Position = u_mvp * vec4(a_pos, 1.0);
}`;

const FRAGMENT = `#version 300 es
precision mediump float;
in vec3 v_pos;
in vec3 v_nrm;
in vec2 v_uv;
uniform vec3 u_color;
uniform float u_metal;
uniform float u_rough;
uniform vec3 u_eye;
uniform int u_textured;
uniform sampler2D u_tex;
out vec4 frag;
void main() {
  vec3 base = u_color;
  if (u_textured == 1) base *= texture(u_tex, v_uv).rgb;
  vec3 n = normalize(v_nrm);
  vec3 v = normalize(u_eye - v_pos);
  vec3 lights[3];
  lights[0] = normalize(vec3(0.45, 0.85, 0.35));
  lights[1] = normalize(vec3(-0.7, 0.25, 0.3));
  lights[2] = normalize(vec3(-0.1, 0.2, -1.0));
  float weight[3];
  weight[0] = 1.0;
  weight[1] = 0.35;
  weight[2] = 0.5;
  vec3 color = base * 0.18;
  for (int i = 0; i < 3; i++) {
    float ndl = max(dot(n, lights[i]), 0.0);
    vec3 h = normalize(lights[i] + v);
    float spec = pow(max(dot(n, h), 0.0), mix(10.0, 80.0, 1.0 - u_rough));
    vec3 diffuse = base * (1.0 - u_metal) * ndl;
    vec3 shine = mix(vec3(0.04), base, u_metal) * spec;
    color += (diffuse + shine) * weight[i];
  }
  float shade = smoothstep(0.35, 0.0, v_pos.y);
  color *= mix(1.0, 0.72, shade);
  frag = vec4(color, 1.0);
}`;

viewer = createViewer(canvas);
draw();
