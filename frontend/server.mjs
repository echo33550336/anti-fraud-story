import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const host = process.env.HOST || '127.0.0.1';
const port = Number(process.env.PORT || 8080);
const upstream = process.env.API_UPSTREAM || 'http://127.0.0.1:5000';
const types = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.png':'image/png', '.webp':'image/webp', '.mp3':'audio/mpeg', '.md':'text/markdown; charset=utf-8' };

createServer(async (req, res) => {
  try {
    const path = new URL(req.url, 'http://localhost').pathname;
    if (path.startsWith('/api/')) {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const target = new URL(req.url, upstream);
      const response = await fetch(target, {
        method: req.method,
        headers: { 'content-type': req.headers['content-type'] || 'application/json' },
        body: chunks.length ? Buffer.concat(chunks) : undefined
      });
      res.writeHead(response.status, { 'content-type': response.headers.get('content-type') || 'application/json; charset=utf-8', 'cache-control':'no-store' });
      res.end(Buffer.from(await response.arrayBuffer()));
      return;
    }
    const local = resolve(root, '.' + decodeURIComponent(path === '/' ? '/index.html' : path));
    if (local !== root && !local.startsWith(root + sep)) { res.writeHead(403); res.end('Forbidden'); return; }
    const info = await stat(local);
    if (!info.isFile()) throw new Error('Not a file');
    const data = await readFile(local);
    res.writeHead(200, { 'content-type': types[extname(local)] || 'application/octet-stream', 'cache-control':'no-store' });
    res.end(data);
  } catch (error) {
    const status = error.code === 'ENOENT' ? 404 : 502;
    res.writeHead(status, { 'content-type':'text/plain; charset=utf-8' });
    res.end(status === 404 ? 'Not Found' : `Service unavailable: ${error.message}`);
  }
}).listen(port, host, () => console.log(`Frontend: http://${host}:${port}  API upstream: ${upstream}`));
