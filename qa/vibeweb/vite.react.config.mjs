import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
export default defineConfig({
  plugins: [react()],
  root: fileURLToPath(new URL("./baselines/react/", import.meta.url)),
  base: "./",
  build: {
    outDir: fileURLToPath(new URL("./dist-react/", import.meta.url)),
    emptyOutDir: true,
  },
});
