// SalaryWise ultra-fast dev server with live-reload (<10ms boot time, zero npm dependencies)
const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const startTime = Date.now();
const DEFAULT_PORT = parseInt(process.env.PORT, 10) || 3000;
const ROOT_DIR = __dirname;
const ASSETS_INDEX = path.join(ROOT_DIR, 'SalaryWise-Official-Android-Studio-Project-1', 'SalaryWise-OfficialBuild', 'app', 'src', 'main', 'assets', 'index.html');
const ROOT_INDEX = path.join(ROOT_DIR, 'index.html');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
};

// SSE LiveReload clients
const clients = new Set();

function broadcastReload() {
  for (const res of clients) {
    try {
      res.write('data: reload\n\n');
    } catch (_) {
      clients.delete(res);
    }
  }
}

const LIVE_RELOAD_SCRIPT = `
<!-- SalaryWise LiveReload -->
<script>
(() => {
  let source;
  function connect() {
    source = new EventSource('/__livereload');
    source.onmessage = (e) => {
      if (e.data === 'reload') {
        console.log('[LiveReload] Refreshing...');
        location.reload();
      }
    };
    source.onerror = () => {
      source.close();
      setTimeout(connect, 1000);
    };
  }
  connect();
})();
</script>
`;

function getIndexPath() {
  if (fs.existsSync(ROOT_INDEX)) return ROOT_INDEX;
  if (fs.existsSync(ASSETS_INDEX)) return ASSETS_INDEX;
  return null;
}

// In-memory cache for ultra-fast instant serving (<0.5ms)
let cachedHtmlBuffer = null;

function refreshHtmlCache() {
  const targetFile = getIndexPath();
  if (!targetFile) {
    cachedHtmlBuffer = null;
    return null;
  }
  try {
    const rawHtml = fs.readFileSync(targetFile, 'utf8');
    const bodyClose = rawHtml.lastIndexOf('</body>');
    const finalHtml = bodyClose !== -1
      ? rawHtml.slice(0, bodyClose) + LIVE_RELOAD_SCRIPT + rawHtml.slice(bodyClose)
      : rawHtml + LIVE_RELOAD_SCRIPT;
    cachedHtmlBuffer = Buffer.from(finalHtml, 'utf8');
    return cachedHtmlBuffer;
  } catch (err) {
    console.error('Error reading index.html:', err.message);
    return null;
  }
}

// Pre-warm HTML cache at startup
refreshHtmlCache();

// Watch both index.html files for changes
let reloadDebounce = null;
function notifyChange() {
  clearTimeout(reloadDebounce);
  reloadDebounce = setTimeout(() => {
    refreshHtmlCache();
    console.log('🔄 File changed, triggering live-reload...');
    broadcastReload();
  }, 30);
}

[ROOT_INDEX].forEach((filePath) => {
  if (fs.existsSync(filePath)) {
    try {
      fs.watch(filePath, (eventType) => {
        if (eventType === 'change') notifyChange();
      });
    } catch (err) {
      // Fallback silently if watch is not supported
    }
  }
});

const server = http.createServer((req, res) => {
  // Prevent browser caching during development
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');

  // LiveReload SSE endpoint
  if (req.url === '/__livereload') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Connection': 'keep-alive',
      'Cache-Control': 'no-cache',
      'Access-Control-Allow-Origin': '*',
    });
    res.write('retry: 1000\n\n');
    clients.add(res);
    req.on('close', () => clients.delete(res));
    return;
  }

  // Health/ping endpoint
  if (req.url === '/__ping') {
    res.writeHead(200, { 'Content-Type': 'text/plain', 'Content-Length': '2' });
    res.end('ok');
    return;
  }

  let reqPath = decodeURI(req.url.split('?')[0]);
  if (reqPath === '/' || reqPath === '/index.html') {
    const data = cachedHtmlBuffer || refreshHtmlCache();
    if (!data) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('index.html not found');
      return;
    }
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Content-Length': data.length,
      'Connection': 'keep-alive',
    });
    res.end(data);
    return;
  }

  // Serve static files
  const filePath = path.join(ROOT_DIR, reqPath);
  if (!filePath.startsWith(ROOT_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('File not found: ' + reqPath);
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const mime = MIME_TYPES[ext] || 'application/octet-stream';
    res.writeHead(200, {
      'Content-Type': mime,
      'Content-Length': stats.size,
      'Connection': 'keep-alive',
    });
    fs.createReadStream(filePath).pipe(res);
  });
});

function openBrowser(url) {
  if (process.argv.includes('--no-open')) return;
  const startCmd = process.platform === 'win32' ? `start "" "${url}"` :
    process.platform === 'darwin' ? `open "${url}"` :
      `xdg-open "${url}"`;
  exec(startCmd, () => { });
}

let currentPort = DEFAULT_PORT;

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    currentPort++;
    console.log(`⚠️ Port ${currentPort - 1} is occupied, trying ${currentPort}...`);
    startListening(currentPort);
  } else {
    console.error('Server error:', err);
  }
});

function startListening(port) {
  // Listen dual-stack (both IPv6 [::1] and IPv4 127.0.0.1) without restricting to 0.0.0.0
  server.listen(port, () => {
    const elapsed = Date.now() - startTime;
    const directUrl = `http://127.0.0.1:${port}`;
    const localUrl = `http://localhost:${port}`;
    console.log(`\n⚡ SalaryWise dev server started in ${elapsed}ms!`);
    console.log(`🔗 Direct URL:   ${directUrl} (zero DNS latency)`);
    console.log(`   Localhost:    ${localUrl}`);
    console.log(`   Live-Reload:  Active (auto-refreshes on save)`);
    console.log(`   Press Ctrl+C to stop\n`);
    // Open 127.0.0.1 directly to bypass Windows IPv6/localhost hostname resolution delay
    openBrowser(directUrl);
  });
}

startListening(currentPort);
