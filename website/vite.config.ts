import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import wasm from "vite-plugin-wasm";
import topLevelAwait from "vite-plugin-top-level-await";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    proxy: {
      "/api/pypi": {
        target: "https://pypistats.org",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/pypi/, "/api"),
      },
      '/proxy/github-api': {
        target: 'https://api.github.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/proxy\/github-api/, ''),
        configure: (proxy, _options) => {
          proxy.on('proxyRes', (proxyRes, _req, _res) => {
            if (proxyRes.headers['location']) {
              proxyRes.headers['location'] = proxyRes.headers['location']
                .replace('https://codeload.github.com', '/proxy/github-codeload');
            }
          });
        },
      },
      '/proxy/github-codeload': {
        target: 'https://codeload.github.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/proxy\/github-codeload/, ''),
      },
      '/proxy/gitlab': {
        target: 'https://gitlab.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/proxy\/gitlab/, ''),
      },
    },
  },
  plugins: [
    react(),
    wasm(),
    topLevelAwait()
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  worker: {
    format: 'es',
    plugins: () => [wasm(), topLevelAwait()],
  },
}));
