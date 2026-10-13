import { defineConfig } from "vite";

export default defineConfig({
  build: {
    lib: {
      entry: new URL("./widget/src/index.ts", import.meta.url).pathname,
      name: "TervoryRig",
      formats: ["es", "umd"],
      fileName: (format) => (format === "umd" ? "tervory-rig.umd.js" : "tervory-rig.js"),
    },
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        chunkFileNames: "tervory-rig-[name].js",
      },
    },
  },
});
