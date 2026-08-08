import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import fs from "fs/promises";
import { parse as urlParse } from "url";

// Vite plugin to run Vercel serverless handlers in local development
function localApiServer() {
  return {
    name: "local-api-server",
    configureServer(server: any) {
      server.middlewares.use(async (req: any, res: any, next: any) => {
        const parsedUrl = urlParse(req.url || "", true);
        const pathname = parsedUrl.pathname || "";
        
        if (pathname.startsWith("/api/")) {
          // Exclude already proxied paths
          if (
            pathname.startsWith("/api/github-zip") ||
            pathname.startsWith("/api/pypi")
          ) {
            return next();
          }

          if (pathname.startsWith("/api/gitlab-zip/")) {
            try {
              const modulePath = path.resolve(__dirname, "./api/gitlab-zip.ts");
              const apiModule = await server.ssrLoadModule(modulePath);
              const handler = apiModule.default || apiModule;
              req.query = parsedUrl.query;
              res.status = (code: number) => {
                res.statusCode = code;
                return res;
              };
              res.json = (data: any) => {
                if (!res.headersSent) {
                  res.setHeader("Content-Type", "application/json");
                }
                res.end(JSON.stringify(data));
                return res;
              };
              await handler(req, res);
            } catch (err: any) {
              console.error("GitLab zip API error:", err);
              if (!res.headersSent) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "GitLab zip proxy failed", details: err.message }));
              }
            }
            return;
          }

          const apiName = pathname.replace("/api/", "");
          try {
            const modulePath = path.resolve(__dirname, `./api/${apiName}.ts`);
            const exists = await fs.access(modulePath).then(() => true).catch(() => false);
            if (!exists) {
              res.statusCode = 404;
              res.end(JSON.stringify({ error: `API endpoint /api/${apiName} not found` }));
              return;
            }

            // Load the API module using Vite's SSR loader (transpiles TS/ESM automatically)
            const apiModule = await server.ssrLoadModule(modulePath);
            const handler = apiModule.default || apiModule;

            // Mock Vercel request & response properties
            req.query = parsedUrl.query;
            
            res.status = (code: number) => {
              res.statusCode = code;
              return res;
            };
            res.json = (data: any) => {
              if (!res.headersSent) {
                res.setHeader("Content-Type", "application/json");
              }
              res.end(JSON.stringify(data));
              return res;
            };

            await handler(req, res);
          } catch (err: any) {
            console.error("Local API execution error:", err);
            if (!res.headersSent) {
              res.statusCode = 500;
              res.end(JSON.stringify({ error: "Local API execution failed", details: err.message }));
            }
          }
          return;
        }
        next();
      });
    }
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load local environment variables (from .env) into process.env so our Vercel handlers can read them
  const env = loadEnv(mode, process.cwd(), "");
  for (const key of Object.keys(env)) {
    process.env[key] = env[key];
  }

  return {
    server: {
      host: "::",
      port: 8080,
      proxy: {
        "/api/github-zip": {
          target: "https://codeload.github.com",
          changeOrigin: true,
          rewrite: (path) => {
            const match = path.match(/^\/api\/github-zip\/([^\/]+)\/([^\/]+)\/([^\/]+)/);
            if (match) {
              const [_, owner, repo, branch] = match;
              return `/${owner}/${repo}/legacy.zip/${branch}`;
            }
            return path;
          },
        },
        "/api/pypi": {
          target: "https://pypistats.org",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/pypi/, "/api"),
        },
      },
    },
    plugins: [react(), localApiServer()].filter(Boolean),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    worker: {
      format: "es",
    },
  };
});
