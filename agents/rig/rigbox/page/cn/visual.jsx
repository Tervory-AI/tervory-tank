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

function link(id, source, target, sourceHandle, targetHandle) {
  return {
    id,
    source,
    target,
    sourceHandle,
    targetHandle,
    type: "straight",
    style: { stroke: "#7ee0d6", strokeWidth: 1.25 },
  };
}

const CENTRE = { w: 240, h: 108 };
const CAT = { w: 156, h: 58 };
const CARD = { w: 248, h: 84 };

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

function columns(model, narrow) {
  const nodes = [];
  const edges = [];
  const groups = model.groups || [];
  const items = model.items || [];
  const centreData = { label: model.centre || "Results", caption: model.caption || "" };
  const pitch = CARD.h + 12;
  if (narrow) {
    let top = 0;
    nodes.push(centreNode(centreData, { x: 8, y: top }));
    top += CENTRE.h + 28;
    groups.forEach((group) => {
      const mine = items.filter((item) => item.category === group.category);
      const id = "cat-" + group.category;
      nodes.push(catNode(group, { x: 8, y: top }));
      top += CAT.h + 16;
      let previous = id;
      mine.forEach((item) => {
        const itemId = "item-" + item.id;
        nodes.push(cardNode(item, { x: 8, y: top }, model.onOpen));
        edges.push(link("e-" + itemId, previous, itemId, "s-b", "t"));
        previous = itemId;
        top += pitch;
      });
      top += 12;
    });
    if (groups[0]) edges.push(link("e-cat-" + groups[0].category, "centre", "cat-" + groups[0].category, "b", "t"));
    return { nodes, edges };
  }
  let cursor = 0;
  const bands = groups.map((group) => {
    const mine = items.filter((item) => item.category === group.category);
    const band = Math.max(pitch, mine.length * pitch);
    const row = { group, mine, top: cursor, band };
    cursor += band + 20;
    return row;
  });
  nodes.push(centreNode(centreData, { x: 0, y: Math.max(0, cursor / 2 - CENTRE.h / 2) }));
  bands.forEach(({ group, mine, top, band }) => {
    const id = "cat-" + group.category;
    nodes.push(catNode(group, { x: 300, y: top + band / 2 - CAT.h / 2 }));
    edges.push(link("e-" + id, "centre", id, "r", "l"));
    mine.forEach((item, index) => {
      const itemId = "item-" + item.id;
      nodes.push(cardNode(item, { x: 500, y: top + index * pitch }, model.onOpen));
      edges.push(link("e-" + itemId, id, itemId, "s-r", "l"));
    });
  });
  return { nodes, edges };
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
  const centre = { x: 250, y: 176 };
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
