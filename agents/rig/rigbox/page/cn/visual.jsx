/** Visual results graph. Bundled to visual.js. React Flow is MIT. */

import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Background, Handle, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const SIDES = [
  ["t", Position.Top],
  ["r", Position.Right],
  ["b", Position.Bottom],
  ["l", Position.Left],
];

function CatNode({ data }) {
  return (
    <div className="cn-node cat">
      {SIDES.map(([id, position]) => (
        <Handle key={"in-" + id} id={id} type="target" position={position} />
      ))}
      {SIDES.map(([id, position]) => (
        <Handle key={"out-" + id} id={"s-" + id} type="source" position={position} />
      ))}
      <span className="cn-node-count">{data.count}</span>
      <strong>{data.label}</strong>
    </div>
  );
}

function CentreNode({ data }) {
  return (
    <div className="cn-node centre">
      <span className="glow" aria-hidden="true" />
      <strong>{data.label}</strong>
      {data.caption ? <span className="centre-caption">{data.caption}</span> : null}
      {SIDES.map(([id, position]) => (
        <Handle key={"out-" + id} id={id} type="source" position={position} />
      ))}
    </div>
  );
}

function CardNode({ data }) {
  return (
    <button type="button" className="cn-node card-node" onClick={() => data.onOpen && data.onOpen(data.id)}>
      <Handle id="t" type="target" position={Position.Top} />
      <Handle id="l" type="target" position={Position.Left} />
      <Handle id="r" type="target" position={Position.Right} />
      <Handle id="s-b" type="source" position={Position.Bottom} />
      <strong>{data.label}</strong>
      <span>{data.meta}</span>
    </button>
  );
}

const nodeTypes = { cat: CatNode, centre: CentreNode, card: CardNode };

function nearestSide(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? "r" : "l";
  return dy >= 0 ? "b" : "t";
}

function opposite(side) {
  return { t: "b", b: "t", l: "r", r: "l" }[side];
}

function link(id, source, target, sourceHandle, targetHandle, type) {
  return {
    id,
    source,
    target,
    sourceHandle,
    targetHandle,
    type: type || "straight",
    style: { stroke: "#7ee0d6", strokeWidth: 1.25 },
  };
}

const CENTRE = { w: 200, h: 200 };
const CAT = { w: 156, h: 58 };
const CARD = { w: 248, h: 88 };
const PITCH = 96;
const GROUP_GAP = 16;
const AFTER_CENTRE = 72;
const GUTTER = 56;

function centreNode(data, position) {
  return {
    id: "centre",
    type: "centre",
    position,
    width: CENTRE.w,
    height: CENTRE.h,
    style: { width: CENTRE.w, height: CENTRE.h },
    data,
    draggable: false,
  };
}

function catNode(group, position) {
  return {
    id: "cat-" + group.category,
    type: "cat",
    position,
    width: CAT.w,
    height: CAT.h,
    style: { width: CAT.w, height: CAT.h },
    data: { label: group.category, count: group.count },
    draggable: false,
  };
}

function cardNode(item, position, onOpen) {
  return {
    id: "item-" + item.id,
    type: "card",
    position,
    width: CARD.w,
    style: { width: CARD.w },
    data: { id: item.id, label: item.name, meta: item.meta, onOpen },
    draggable: false,
  };
}

function bandFor(count) {
  const n = Math.max(count, 1);
  return Math.max(CAT.h, (n - 1) * PITCH + CARD.h);
}

function splitColumns(groups, items) {
  const cols = [[], []];
  const weight = [0, 0];
  groups.forEach((group) => {
    const n = items.filter((item) => item.category === group.category).length;
    const side = weight[0] <= weight[1] ? 0 : 1;
    cols[side].push(group);
    weight[side] += Math.max(n, 1);
  });
  return cols;
}

function placeColumn(groups, items, xCat, y0, nodes, edges, onOpen, cardsOnRight) {
  let y = y0;
  let previousCat = "";
  groups.forEach((group) => {
    const mine = items.filter((item) => item.category === group.category);
    const id = "cat-" + group.category;
    nodes.push(catNode(group, { x: xCat, y }));
    if (!previousCat) edges.push(link("e-" + id, "centre", id, "b", "t"));
    else edges.push(link("e-" + id, previousCat, id, "s-b", "t"));
    const cardX = cardsOnRight ? xCat + CAT.w + GUTTER : xCat - CARD.w - GUTTER;
    mine.forEach((item, index) => {
      const itemId = "item-" + item.id;
      nodes.push(cardNode(item, { x: cardX, y: y + index * PITCH }, onOpen));
      edges.push(link(
        "e-" + itemId,
        id,
        itemId,
        cardsOnRight ? "s-r" : "s-l",
        cardsOnRight ? "l" : "r",
        "smoothstep",
      ));
    });
    previousCat = id;
    y += bandFor(mine.length) + GROUP_GAP;
  });
  return y;
}

function columns(model, narrow) {
  const nodes = [];
  const edges = [];
  const groups = model.groups || [];
  const items = model.items || [];
  const centreData = { label: model.centre || "Results", caption: model.caption || "" };
  if (narrow) {
    let top = 0;
    nodes.push(centreNode(centreData, { x: 8, y: top }));
    top += CENTRE.h + 28;
    groups.forEach((group) => {
      const mine = items.filter((item) => item.category === group.category);
      const id = "cat-" + group.category;
      nodes.push(catNode(group, { x: 8, y: top }));
      top += CAT.h + 16;
      mine.forEach((item) => {
        const itemId = "item-" + item.id;
        nodes.push(cardNode(item, { x: 8, y: top }, model.onOpen));
        edges.push(link("e-" + itemId, id, itemId, "s-b", "t", "smoothstep"));
        top += PITCH;
      });
      top += 12;
    });
    if (groups[0]) edges.push(link("e-cat-" + groups[0].category, "centre", "cat-" + groups[0].category, "b", "t"));
    return { nodes, edges };
  }
  const cols = splitColumns(groups, items);
  const leftCat = CARD.w + GUTTER;
  const rightCat = leftCat + CAT.w + 80;
  const rightCards = rightCat + CAT.w + GUTTER;
  const block = rightCards + CARD.w;
  const catSpan = rightCat + CAT.w - leftCat;
  nodes.push(centreNode(centreData, {
    x: leftCat + Math.max(0, (catSpan - CENTRE.w) / 2),
    y: 0,
  }));
  const y0 = CENTRE.h + AFTER_CENTRE;
  placeColumn(cols[0], items, leftCat, y0, nodes, edges, model.onOpen, false);
  placeColumn(cols[1], items, rightCat, y0, nodes, edges, model.onOpen, true);
  return { nodes, edges, width: block };
}

function orbit(model, narrow) {
  const groups = model.groups || [];
  const n = Math.max(groups.length, 1);
  const nodes = [];
  const edges = [];
  if (narrow) {
    const centre = { x: 8, y: 8 };
    nodes.push(centreNode(
      { label: model.centre || "Ready when you are.", caption: model.caption || "" },
      centre,
    ));
    groups.forEach((group, index) => {
      const col = index % 2;
      const row = Math.floor(index / 2);
      const position = {
        x: 8 + col * (CAT.w + 16),
        y: centre.y + CENTRE.h + 36 + row * (CAT.h + 16),
      };
      const id = "cat-" + group.category;
      nodes.push(catNode(group, position));
      const above = row > 0 ? groups[index - 2] : null;
      edges.push(above
        ? link("e-" + id, "cat-" + above.category, id, "s-b", "t")
        : link("e-" + id, "centre", id, "b", "t"));
    });
    return { nodes, edges };
  }
  const centre = { x: 250, y: 200 };
  const mid = { x: centre.x + CENTRE.w / 2, y: centre.y + CENTRE.h / 2 };
  const clear = Math.hypot(CENTRE.w / 2, CENTRE.h / 2) + Math.hypot(CAT.w / 2, CAT.h / 2) + 28;
  const apart = (Math.max(CAT.w, CAT.h) + 24) / (2 * Math.sin(Math.PI / n));
  const radius = Math.max(clear, apart);
  nodes.push(centreNode(
    { label: model.centre || "Ready when you are.", caption: model.caption || "" },
    centre,
  ));
  groups.forEach((group, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / n;
    const id = "cat-" + group.category;
    const position = {
      x: mid.x + Math.cos(angle) * radius - CAT.w / 2,
      y: mid.y + Math.sin(angle) * radius - CAT.h / 2,
    };
    nodes.push(catNode(group, position));
    const from = nearestSide(mid, { x: position.x + CAT.w / 2, y: position.y + CAT.h / 2 });
    edges.push(link("e-" + id, "centre", id, from, opposite(from)));
  });
  return { nodes, edges };
}

function Graph({ model }) {
  const [narrow, setNarrow] = useState(() => window.innerWidth < 800);
  useEffect(() => {
    const apply = () => setNarrow(window.innerWidth < 800);
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, []);
  const laid = model.layout === "orbit" ? orbit(model, narrow) : columns(model, narrow);
  return (
    <ReactFlow
      key={narrow ? "narrow" : "wide"}
      nodes={laid.nodes}
      edges={laid.edges}
      nodeTypes={nodeTypes}
      fitView
      minZoom={0.82}
      fitViewOptions={{ padding: 0.08, minZoom: 0.82, maxZoom: 1 }}
      maxZoom={1.25}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      proOptions={{ hideAttribution: false }}
      onNodeClick={(_, node) => {
        if (node.data && node.data.id && model.onOpen) model.onOpen(node.data.id);
      }}
    >
      <Background color="#1d3a34" gap={22} />
    </ReactFlow>
  );
}

const roots = new WeakMap();

function mount(element, model) {
  let root = roots.get(element);
  if (!root) {
    root = createRoot(element);
    roots.set(element, root);
  }
  root.render(<Graph model={model || {}} />);
  return () => {
    root.unmount();
    roots.delete(element);
  };
}

window.CNVisual = { mount };
