import { TervoryRig } from "./element";

if (!customElements.get("tervory-rig")) {
  customElements.define("tervory-rig", TervoryRig);
}

export { TervoryRig };
export { RigClient } from "./api/client";
export { customNation, neutral, resolveTheme } from "./theme/themes";
export type { Theme } from "./theme/themes";
