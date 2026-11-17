import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "node:url";
export default defineConfig({
  plugins: [svelte()],
  root: fileURLToPath(new URL("./baselines/svelte/", import.meta.url)),
  base: "./",
  build: {
    outDir: fileURLToPath(new URL("./dist-svelte/", import.meta.url)),
    emptyOutDir: true,
  },
});
