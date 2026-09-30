#!/usr/bin/env node
// ASR 전사 시험 페이지.
// node r2t2-live-test/server.mjs
// getUserMedia는 보안 컨텍스트에서만 열리므로 file:// 대신 localhost로 띄운다.
// ASR 서버에 CORS 헤더가 없어서, 브라우저 대신 이 서버가 POST를 넘겨준다.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const publicDir = fileURLToPath(new URL("./public/", import.meta.url));
const port = Number(process.env.PORT || 8792);
const MAX_BODY = 100 * 1024 * 1024;
const UPSTREAM_TIMEOUT_MS = 300_000;

const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

function sendJson(res, status, body) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

async function readBody(req) {
  const parts = [];
  let size = 0;
  for await (const part of req) {
    size += part.length;
    if (size > MAX_BODY) throw new Error("too large");
    parts.push(part);
  }
  return Buffer.concat(parts);
}

async function proxy(req, res, target) {
  let url;
  try {
    url = new URL(target || "");
  } catch {}
  if (!url || (url.protocol !== "http:" && url.protocol !== "https:")) {
    sendJson(res, 400, { detail: "target은 http(s) 주소여야 합니다." });
    return;
  }
  let body;
  try {
    body = await readBody(req);
  } catch {
    sendJson(res, 413, { detail: "파일이 100MB를 넘습니다." });
    return;
  }
  try {
    const upstream = await fetch(url, {
      method: "POST",
      headers: { "content-type": req.headers["content-type"] || "application/octet-stream" },
      body,
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    res.writeHead(upstream.status, {
      "content-type": upstream.headers.get("content-type") || "text/plain; charset=utf-8",
    });
    res.end(Buffer.from(await upstream.arrayBuffer()));
  } catch (err) {
    const reason = err && err.name === "TimeoutError" ? "응답 시간 초과" : (err && err.cause && err.cause.code) || String(err);
    sendJson(res, 502, { detail: `ASR 서버에 닿지 못했습니다 (${reason}).` });
  }
}

const server = createServer(async (req, res) => {
  const reqUrl = new URL(req.url, "http://localhost");
  if (reqUrl.pathname === "/api/transcribe") {
    if (req.method !== "POST") {
      sendJson(res, 405, { detail: "POST만 받습니다." });
      return;
    }
    await proxy(req, res, reqUrl.searchParams.get("target"));
    return;
  }
  const path = reqUrl.pathname;
  const file = normalize(join(publicDir, path === "/" ? "index.html" : path));
  if (!file.startsWith(publicDir) || !types[extname(file)]) {
    res.writeHead(404).end("not found");
    return;
  }
  try {
    const body = await readFile(file);
    res.writeHead(200, { "content-type": types[extname(file)], "cache-control": "no-store" });
    res.end(body);
  } catch {
    res.writeHead(404).end("not found");
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`ASR 전사 시험 페이지: http://localhost:${port}`);
});
