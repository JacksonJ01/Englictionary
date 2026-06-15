import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import http from "node:http";
import path from "node:path";

import { exists, prepareVercelArtifacts } from "./vercel-pipeline.js";

const ROOT = process.cwd();
const PORT = Number(process.env.PORT || 4173);

const MIME_TYPES: Record<string, string> = {
  ".css": "text/css; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".gif": "image/gif",
  ".htm": "text/html; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".webp": "image/webp"
};

function contentTypeFor(filePath: string): string {
  return MIME_TYPES[path.extname(filePath).toLowerCase()] || "application/octet-stream";
}

function sendFile(response: http.ServerResponse, filePath: string): void {
  response.writeHead(200, { "Content-Type": contentTypeFor(filePath) });
  createReadStream(filePath).pipe(response);
}

async function resolveRequestPath(urlPath: string, targetHtml: string): Promise<string | null> {
  if (urlPath === "/" || urlPath === "/spherical") {
    return targetHtml;
  }

  const normalized = path.normalize(decodeURIComponent(urlPath)).replace(/^([.][.][/\\])+/, "");
  const candidate = path.join(ROOT, normalized.replace(/^[/\\]+/, ""));

  if (await exists(candidate)) {
    return candidate;
  }

  if (!path.extname(candidate)) {
    const htmlCandidate = `${candidate}.html`;
    if (await exists(htmlCandidate)) {
      return htmlCandidate;
    }
  }

  return null;
}

async function main(): Promise<void> {
  const { targetHtml } = await prepareVercelArtifacts();

  const server = http.createServer(async (request, response) => {
    const requestUrl = new URL(request.url || "/", `http://${request.headers.host || `localhost:${PORT}`}`);
    const filePath = await resolveRequestPath(requestUrl.pathname, targetHtml);

    if (!filePath) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }

    try {
      const fileStat = await stat(filePath);
      if (!fileStat.isFile()) {
        response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Not found");
        return;
      }
      sendFile(response, filePath);
    } catch {
      response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Failed to read file");
    }
  });

  server.listen(PORT, () => {
    console.log(`Local preview available at http://localhost:${PORT}`);
    console.log(`Serving Vercel-equivalent spherical route at http://localhost:${PORT}/spherical`);
  });
}

await main();