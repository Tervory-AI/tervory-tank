export const styles = `
:host {
  all: initial;
  display: block;
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  color: var(--rig-ink, #242722);
  background: var(--rig-canvas, #f2efe7);
  font-family: var(--rig-font-body, Inter, sans-serif);
  font-size: 16px;
  line-height: 1.4;
  box-sizing: border-box;
}
:host(.is-explore) {
  background: var(--rig-graph-canvas, #121510);
  color: var(--rig-graph-text, #fcfaf4);
}
*, *::before, *::after { box-sizing: border-box; }
button, input, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
img { max-width: 100%; display: block; }
p, h1, h2 { margin: 0; }
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
:focus-visible {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.shell {
  width: min(1200px, 100%);
  margin: 0 auto;
  padding: 40px 48px 48px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.shell-explore {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
  gap: 0;
}
.header, .brand-row, .meta-row, .price-row, .part, .actions, .tier-row, .link-row, .popular {
  display: flex;
  align-items: center;
}
.header { gap: 12px; }
.dash { width: 28px; height: 2px; background: var(--rig-accent); flex: none; }
.eyebrow {
  margin: 0;
  color: var(--rig-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.mark {
  margin-left: auto;
  color: var(--rig-faint);
  font-size: 11px;
  font-weight: 500;
}
h1.title {
  font-family: var(--rig-font-heading);
  font-weight: 600;
  font-size: 56px;
  line-height: 1;
  letter-spacing: 0;
  text-transform: uppercase;
  color: var(--rig-ink);
}
.search {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--rig-card);
  border: 2px solid var(--rig-ink);
  border-radius: var(--rig-radius);
  padding: 8px 8px 8px 22px;
}
.search-icon { color: var(--rig-muted); font-size: 22px; line-height: 1; }
.search input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  font-size: 18px;
  padding: 8px 0;
  outline: none;
}
.search input::placeholder { color: var(--rig-faint); }
.search:focus-within {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.btn {
  border-radius: var(--rig-radius);
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  padding: 14px 22px;
  white-space: nowrap;
}
.btn-accent {
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  border: 2px solid var(--rig-accent);
}
.btn-ghost {
  background: transparent;
  color: var(--rig-ink);
  border: 1px solid var(--rig-ink);
}
.btn-selected {
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  border: 2px solid var(--rig-accent);
}
.text-btn {
  background: none;
  border: 0;
  padding: 0;
  color: var(--rig-muted);
  font-size: 13px;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.popular { flex-wrap: wrap; gap: 8px; }
.popular-label { color: var(--rig-muted); font-size: 12px; font-weight: 600; }
.chip {
  background: transparent;
  color: var(--rig-ink);
  border: 1px solid var(--rig-ink);
  border-radius: var(--rig-radius);
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 500;
}
.steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.step {
  border-top: 2px solid var(--rig-accent);
  padding-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.step-no {
  font-family: var(--rig-font-heading);
  font-size: 24px;
  font-weight: 600;
  color: var(--rig-accent);
  line-height: 1;
}
.step h2, .kicker, .card-name, .setup-name, .panel h2, .centre h2, .missing h2, .quote h2 {
  font-family: var(--rig-font-heading);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0;
}
.step h2 { font-size: 22px; line-height: 1.15; }
.step p, .fine, .missing-copy, .label, .summary, .fit-line { color: var(--rig-muted); }
.step p { font-size: 14px; }
.meta-row { gap: 10px; flex-wrap: wrap; }
.meta-row strong { font-size: 13px; }
.sample {
  display: inline-block;
  background: var(--rig-badge);
  color: var(--rig-muted);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 3px 6px;
  border-radius: var(--rig-radius);
  white-space: nowrap;
}
.cards, .setups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.card, .setup {
  background: var(--rig-card);
  border: 2px solid transparent;
  border-radius: var(--rig-radius);
  padding: 16px 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.card.selected { border-color: var(--rig-accent); }
.photo {
  background: var(--rig-card);
  border: 1px solid var(--rig-line);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--rig-faint);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  overflow: hidden;
}
.photo-lg { height: 200px; width: 100%; }
.photo-sm { width: 120px; height: 80px; flex: none; }
.photo-xs { width: 64px; height: 48px; flex: none; }
.photo img { width: 100%; height: 100%; object-fit: contain; }
.brand-row { justify-content: space-between; gap: 8px; }
.brand {
  color: var(--rig-accent);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.card-name { font-size: 28px; line-height: 1; }
.summary { font-size: 13px; }
.price-row { gap: 8px; align-items: baseline; flex-wrap: wrap; }
.price-cap {
  color: var(--rig-muted);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
}
.price {
  font-family: var(--rig-font-heading);
  font-weight: 600;
  font-size: 30px;
  line-height: 1;
}
.price-lg { font-size: 36px; }
.actions { gap: 8px; flex-wrap: wrap; }
.chosen {
  background: var(--rig-card);
  border-radius: var(--rig-radius);
  padding: 14px 16px;
  display: flex;
  gap: 20px;
  align-items: center;
}
.chosen-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.you-chose {
  color: var(--rig-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.chosen h2 {
  font-family: var(--rig-font-heading);
  font-size: 26px;
  font-weight: 600;
  text-transform: uppercase;
  line-height: 1.05;
}
.chosen-note { color: var(--rig-muted); font-size: 13px; }
.chosen-side { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.kicker-row { display: flex; align-items: center; gap: 12px; }
.kicker-bar { width: 4px; height: 28px; background: var(--rig-accent); flex: none; }
.kicker { font-size: 32px; line-height: 1; }
.setup { padding: 20px 20px 22px; gap: 12px; }
.setup.featured {
  background: var(--rig-featured);
  color: var(--rig-featured-text);
}
.setup.featured .label,
.setup.featured .fit-line,
.setup.featured .price-cap,
.setup.featured .swap-btn { color: var(--rig-featured-muted); }
.setup-head { display: flex; align-items: center; gap: 8px; }
.setup-no {
  font-family: var(--rig-font-heading);
  font-size: 22px;
  font-weight: 600;
  color: var(--rig-accent);
}
.setup-name { font-size: 26px; line-height: 1; }
.setup-head .badge-hot,
.setup-head .sample:last-child { margin-left: auto; }
.badge-hot {
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 4px 7px;
  border-radius: var(--rig-radius);
}
.label { font-size: 13px; }
.part {
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--rig-line);
}
.setup.featured .part { border-bottom-color: rgba(252, 250, 244, 0.15); }
.part-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.role {
  color: var(--rig-accent);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.part-name { font-size: 14px; font-weight: 500; }
.swap-btn {
  background: none;
  border: 0;
  color: var(--rig-muted);
  font-size: 11px;
  font-weight: 600;
  padding: 4px;
  white-space: nowrap;
}
.fit-line { font-size: 11px; }
.quote-wide { width: 100%; }
.fine { font-size: 12px; }
.options {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 8px;
}
.option {
  text-align: left;
  background: transparent;
  border: 1px solid var(--rig-line-strong);
  border-radius: var(--rig-radius);
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 500;
}
.setup.featured .option { border-color: rgba(252, 250, 244, 0.3); color: var(--rig-featured-text); }
.missing {
  background: var(--rig-card);
  border-radius: var(--rig-radius);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.missing h2 { font-size: 30px; line-height: 1.05; }
.missing-copy { font-size: 15px; }
.field, .link-url {
  width: 100%;
  background: var(--rig-card);
  border: 1px solid var(--rig-line-strong);
  border-radius: var(--rig-radius);
  padding: 13px 14px;
  font-size: 14px;
  outline: none;
}
.field::placeholder, .link-url::placeholder { color: var(--rig-faint); }
.field:focus,
.field:focus-visible,
.link-url:focus,
.link-url:focus-visible {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.link-row { gap: 10px; align-items: center; }
.link-url { flex: 1; min-width: 0; }
.note { display: flex; flex-direction: column; gap: 6px; }
.note span { font-size: 12px; font-weight: 600; color: var(--rig-muted); }
.status { color: var(--rig-accent); font-size: 14px; }
.ack { color: var(--rig-ink); font-size: 14px; font-weight: 600; }
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(36, 39, 34, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 5;
}
.quote {
  width: min(420px, 100%);
  background: var(--rig-card);
  color: var(--rig-ink);
  border-radius: var(--rig-radius);
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.quote h2 { font-size: 28px; }
.quote label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.explore { position: relative; min-height: 640px; }
.explore-header {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 56px;
  padding: 10px 32px;
  background: color-mix(in srgb, var(--rig-graph-canvas) 60%, transparent);
}
.explore-header h1 {
  font-family: var(--rig-font-heading);
  font-size: 22px;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
}
.explore-search {
  margin: 0 auto;
  width: min(420px, 100%);
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--rig-graph-line);
  border-radius: 999px;
  padding: 6px 8px 6px 14px;
}
.explore-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--rig-graph-text);
  font-size: 14px;
  outline: none;
}
.explore-search input::placeholder { color: var(--rig-graph-muted); }
.explore-search:focus-within {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.explore-mark { color: var(--rig-graph-muted); font-size: 11px; font-weight: 500; white-space: nowrap; }
.back {
  background: none;
  border: 0;
  color: var(--rig-graph-muted);
  font-size: 13px;
  font-weight: 600;
  padding: 0;
}
.explore-grid {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr) minmax(260px, 400px);
  gap: 16px 20px;
  padding: 28px 32px 24px;
  align-items: start;
  min-height: 720px;
}
.graph { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.branch-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 280px);
  gap: 16px;
  align-items: start;
}
.centre { display: flex; flex-direction: column; align-items: center; text-align: center; padding-top: 36px; }
.orb-wrap { position: relative; width: 220px; height: 220px; display: grid; place-items: center; }
.orb {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, color-mix(in srgb, var(--rig-accent) 65%, white), var(--rig-accent) 58%, color-mix(in srgb, var(--rig-accent) 35%, black));
  box-shadow:
    0 0 0 22px color-mix(in srgb, var(--rig-accent) 28%, transparent),
    0 0 0 48px color-mix(in srgb, var(--rig-accent) 14%, transparent),
    0 0 0 78px color-mix(in srgb, var(--rig-accent) 7%, transparent),
    0 0 40px color-mix(in srgb, var(--rig-accent) 50%, transparent);
}
.orb-label {
  position: absolute;
  top: 18px;
  color: var(--rig-accent);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.centre h2 { font-size: 26px; margin-top: 8px; color: var(--rig-graph-text); }
.centre p { color: var(--rig-graph-muted); font-size: 11px; }
.branches, .products { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.branch, .g-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  background: var(--rig-graph-chip);
  color: var(--rig-graph-text);
  border: 1px solid var(--rig-graph-line);
  border-radius: var(--rig-radius-graph);
  padding: 6px 10px;
}
.branch.on, .g-chip.on {
  background: var(--rig-graph-chip-on);
  border-color: var(--rig-accent);
}
.branch .count {
  font-family: var(--rig-font-heading);
  font-size: 24px;
  font-weight: 600;
  line-height: 1;
  min-width: 1.4em;
}
.branch .cat {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--rig-graph-muted);
}
.swatch {
  width: 30px;
  height: 30px;
  border-radius: 4px;
  background: var(--rig-card);
  flex: none;
}
.g-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.g-name { font-size: 12px; font-weight: 500; }
.g-meta { font-size: 10px; color: var(--rig-graph-muted); }
.more { color: var(--rig-graph-muted); font-size: 11px; margin: 0 0 8px; }
.side { display: flex; flex-direction: column; gap: 16px; min-height: 100%; }
.panel {
  background: color-mix(in srgb, var(--rig-graph-raised) 92%, transparent);
  border: 1px solid var(--rig-graph-line);
  border-radius: calc(var(--rig-radius-graph) + 4px);
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.panel-kicker {
  color: var(--rig-accent);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.panel h2 {
  font-size: 26px;
  line-height: 1.05;
  text-transform: none;
  color: var(--rig-graph-text);
}
.panel-body { color: var(--rig-graph-muted); font-size: 13px; line-height: 1.5; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.stat {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--rig-radius-graph);
  padding: 10px 12px;
}
.stat strong {
  display: block;
  font-family: var(--rig-font-heading);
  font-size: 26px;
  font-weight: 600;
  line-height: 1;
}
.stat span { color: var(--rig-graph-muted); font-size: 11px; }
.tier-row { gap: 6px; flex-wrap: wrap; }
.tier {
  background: transparent;
  color: var(--rig-graph-text);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 11px;
  font-weight: 600;
}
.tier.on { background: var(--rig-accent); border-color: transparent; }
.why {
  background: rgba(255, 255, 255, 0.04);
  border-radius: var(--rig-radius-graph);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.why strong { font-size: 12px; }
.why p { color: var(--rig-graph-muted); font-size: 12px; }
.ask {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  padding: 8px 8px 8px 16px;
  margin-top: auto;
}
.ask input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--rig-graph-text);
  font-size: 13px;
  outline: none;
}
.ask input::placeholder { color: var(--rig-graph-muted); }
.ask:focus-within {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.ask-go {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 0;
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  font-weight: 600;
  flex: none;
}
.answer { color: var(--rig-graph-text); font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
.answer span { color: var(--rig-graph-muted); font-size: 11px; }
.sample-float { position: absolute; left: 32px; bottom: 20px; background: rgba(255, 255, 255, 0.08); color: var(--rig-graph-muted); }
@media (max-width: 1100px) {
  .explore-grid { grid-template-columns: 1fr; min-height: 0; padding: 16px; }
  .branch-row { grid-template-columns: 1fr; }
  .explore-header { flex-wrap: wrap; padding: 12px 16px; }
  .explore-header h1 { font-size: 18px; white-space: normal; }
  .explore > .status { padding: 0 16px; }
  .explore-search { order: 3; width: 100%; margin: 0; }
  .centre { padding-top: 8px; }
  .side { min-height: 0; }
  .ask { margin-top: 0; }
  .sample-float { position: static; margin: 0 16px 16px; }
}
@media (max-width: 720px) {
  .shell { padding: 20px 16px 28px; gap: 18px; }
  h1.title { font-size: 34px; }
  .steps, .cards, .setups { grid-template-columns: 1fr; }
  .search { padding-left: 12px; gap: 8px; }
  .search input { font-size: 16px; }
  .actions { flex-direction: column; align-items: stretch; }
  .actions .btn { width: 100%; text-align: center; }
  .chosen { flex-wrap: wrap; }
  .chosen-side { flex-direction: row; align-items: center; width: 100%; justify-content: space-between; }
  .kicker { font-size: 26px; }
  .link-row { flex-direction: column; align-items: stretch; }
  .price-lg { font-size: 32px; }
  .card-name { overflow-wrap: anywhere; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
`;
