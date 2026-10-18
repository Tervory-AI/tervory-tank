/** Visual results graph. Bundled to visual.js. React Flow is MIT. */

import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Background, Handle, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

function CatNode({ data }) {
  return (
    <div className="cn-node cat">
      <span className="cn-node-count">{data.count}</span>
      <strong>{data.label}</strong>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function CentreNode({ data }) {
  return (
    <div className="cn-node centre">
      <Handle type="target" position={Position.Left} />
      <span className="glow" aria-hidden="true" />
      <strong>{data.label}</strong>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function CardNode({ data }) {
  return (
    <button type="button" className="cn-node card-node" onClick={() => data.onOpen && data.onOpen(data.id)}>
      <Handle type="target" position={Position.Left} />
      <strong>{data.label}</strong>
      <span>{data.meta}</span>
    </button>
  );
}

const nodeTypes = { cat: CatNode, centre: CentreNode, card: CardNode };

function columns(model, narrow) {
  const nodes = [];
  const edges = [];
  const groups = model.groups || [];
  const items = model.items || [];
  if (narrow) {
    const blocks = [];
    groups.forEach((group) => {
      blocks.push({ kind: "cat", group });
      items.filter((item) => item.category === group.category).forEach((item) => {
        blocks.push({ kind: "card", item });
      });
    });
    const heightOf = (block) => (block.kind === "cat" ? 72 : 88);
    const total = blocks.reduce((sum, block) => sum + heightOf(block), 0);
    const middle = total / 2;
    let top = 0;
    let placed = false;
    const centreAt = (y) => {
      nodes.push({
        id: "centre",
        type: "centre",
        position: { x: 16, y },
        data: { label: model.centre || "Results" },
        draggable: false,
      });
    };
    blocks.forEach((block) => {
      if (!placed && top >= middle) {
        centreAt(top);
        top += 96;
        placed = true;
      }
      if (block.kind === "cat") {
        const id = "cat-" + block.group.category;
        nodes.push({
          id,
          type: "cat",
          position: { x: 0, y: top },
          data: { label: block.group.category, count: block.group.count },
          draggable: false,
        });
        edges.push({
          id: "e-" + id,
          source: id,
          target: "centre",
          style: { stroke: "#7ee0d6", strokeWidth: 1.25 },
        });
      } else {
        const itemId = "item-" + block.item.id;
        nodes.push({
          id: itemId,
          type: "card",
          position: { x: 0, y: top },
          data: { id: block.item.id, label: block.item.name, meta: block.item.meta, onOpen: model.onOpen },
          draggable: false,
        });
        edges.push({
          id: "e-" + itemId,
          source: "centre",
          target: itemId,
          style: { stroke: "#2f6f68", strokeWidth: 1 },
        });
      }
      top += heightOf(block);
    });
    if (!placed) centreAt(top);
    return { nodes, edges };
  }
  let cursor = 0;
  const bands = groups.map((group) => {
    const mine = items.filter((item) => item.category === group.category);
    const band = Math.max(96, mine.length * 92);
    const row = { group, mine, top: cursor, band };
    cursor += band + 16;
    return row;
  });
  nodes.push({
    id: "centre",
    type: "centre",
    position: { x: 300, y: Math.max(0, cursor / 2 - 48) },
    data: { label: model.centre || "Results" },
    draggable: false,
  });
  bands.forEach(({ group, mine, top, band }) => {
    const id = "cat-" + group.category;
    nodes.push({
      id,
      type: "cat",
      position: { x: 0, y: top + band / 2 - 28 },
      data: { label: group.category, count: group.count },
      draggable: false,
    });
    edges.push({
      id: "e-" + id,
      source: id,
      target: "centre",
      style: { stroke: "#7ee0d6", strokeWidth: 1.25 },
    });
    mine.forEach((item, index) => {
      const itemId = "item-" + item.id;
      nodes.push({
        id: itemId,
        type: "card",
        position: { x: 560, y: top + index * 92 },
        data: { id: item.id, label: item.name, meta: item.meta, onOpen: model.onOpen },
        draggable: false,
      });
      edges.push({
        id: "e-" + itemId,
        source: "centre",
        target: itemId,
        style: { stroke: "#2f6f68", strokeWidth: 1 },
      });
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
      data: { label: model.centre || "Ready when you are." },
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
      minZoom={0.8}
      fitViewOptions={{ minZoom: 0.8, padding: 0.12 }}
      maxZoom={1.4}
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
