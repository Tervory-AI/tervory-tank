/** Visual results graph. Bundled to visual.js. React Flow is MIT. */

import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Background, Handle, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

function CatNode({ data }) {
  const vertical = !!data.vertical;
  return (
    <div className="cn-node cat">
      <Handle type="target" position={vertical ? Position.Top : Position.Left} />
      <span className="cn-node-count">{data.count}</span>
      <strong>{data.label}</strong>
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} />
    </div>
  );
}

function CentreNode({ data }) {
  const vertical = !!data.vertical;
  return (
    <div className="cn-node centre">
      <Handle type="target" position={vertical ? Position.Top : Position.Left} />
      <span className="glow" aria-hidden="true" />
      <strong>{data.label}</strong>
      {data.caption ? <span className="centre-caption">{data.caption}</span> : null}
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} />
    </div>
  );
}

function CardNode({ data }) {
  return (
    <button type="button" className="cn-node card-node" onClick={() => data.onOpen && data.onOpen(data.id)}>
      <Handle type="target" position={data.vertical ? Position.Top : Position.Left} />
      <strong>{data.label}</strong>
      <span>{data.meta}</span>
    </button>
  );
}

const nodeTypes = { cat: CatNode, centre: CentreNode, card: CardNode };

function edge(id, source, target) {
  return { id, source, target, type: "smoothstep", style: { stroke: "#7ee0d6", strokeWidth: 1.25 } };
}

function columns(model, narrow) {
  const nodes = [];
  const edges = [];
  const groups = model.groups || [];
  const items = model.items || [];
  const centreData = { label: model.centre || "Results", caption: model.caption || "" };
  if (narrow) {
    let top = 0;
    nodes.push({
      id: "centre",
      type: "centre",
      position: { x: 40, y: top },
      data: { ...centreData, vertical: true },
      draggable: false,
    });
    top += 110;
    groups.forEach((group) => {
      const mine = items.filter((item) => item.category === group.category);
      const id = "cat-" + group.category;
      nodes.push({
        id,
        type: "cat",
        position: { x: 48, y: top },
        data: { label: group.category, count: group.count, vertical: true },
        draggable: false,
      });
      edges.push(edge("e-" + id, "centre", id));
      top += 64;
      mine.forEach((item) => {
        const itemId = "item-" + item.id;
        nodes.push({
          id: itemId,
          type: "card",
          position: { x: 8, y: top },
          data: { id: item.id, label: item.name, meta: item.meta, onOpen: model.onOpen, vertical: true },
          draggable: false,
        });
        edges.push(edge("e-" + itemId, id, itemId));
        top += 72;
      });
      top += 16;
    });
    return { nodes, edges };
  }
  let cursor = 0;
  const bands = groups.map((group) => {
    const mine = items.filter((item) => item.category === group.category);
    const band = Math.max(52, mine.length * 46);
    const row = { group, mine, top: cursor, band };
    cursor += band + 10;
    return row;
  });
  nodes.push({
    id: "centre",
    type: "centre",
    position: { x: 0, y: Math.max(0, cursor / 2 - 36) },
    data: centreData,
    draggable: false,
  });
  bands.forEach(({ group, mine, top, band }) => {
    const id = "cat-" + group.category;
    nodes.push({
      id,
      type: "cat",
      position: { x: 210, y: top + band / 2 - 22 },
      data: { label: group.category, count: group.count },
      draggable: false,
    });
    edges.push(edge("e-" + id, "centre", id));
    mine.forEach((item, index) => {
      const itemId = "item-" + item.id;
      nodes.push({
        id: itemId,
        type: "card",
        position: { x: 360, y: top + index * 46 },
        data: { id: item.id, label: item.name, meta: item.meta, onOpen: model.onOpen },
        draggable: false,
      });
      edges.push(edge("e-" + itemId, id, itemId));
    });
  });
  return { nodes, edges };
}

function orbit(model, narrow) {
  const groups = model.groups || [];
  const spanX = narrow ? 110 : 230;
  const spanY = narrow ? 90 : 150;
  const originX = narrow ? 90 : 270;
  const originY = narrow ? 150 : 180;
  const nodes = [
    {
      id: "centre",
      type: "centre",
      position: { x: narrow ? 70 : 250, y: narrow ? 140 : 170 },
      data: { label: model.centre || "Ready when you are.", caption: model.caption || "" },
      draggable: false,
    },
  ];
  const edges = [];
  groups.forEach((group, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / Math.max(groups.length, 1);
    const id = "cat-" + group.category;
    nodes.push({
      id,
      type: "cat",
      position: { x: originX + Math.cos(angle) * spanX, y: originY + Math.sin(angle) * spanY },
      data: { label: group.category, count: group.count },
      draggable: false,
    });
    edges.push({
      id: "e-" + id,
      source: id,
      target: "centre",
      style: { stroke: "#7ee0d6", strokeWidth: 1.25 },
    });
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
      minZoom={0.35}
      fitViewOptions={{ padding: 0.08, minZoom: 0.35, maxZoom: 1.15 }}
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
