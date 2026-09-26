import { defineConfig } from "vite";

export default defineConfig({
    root: ".",
    build: {
        outDir: "dist",
        rollupOptions: {
            input: {
                index: "index.html",
                verify: "verify.html",
            },
        },
    },
    server: {
        proxy: {
            "/api": {
                target: "http://localhost:8080",
                changeOrigin: true,
            },
        },
    },
});
