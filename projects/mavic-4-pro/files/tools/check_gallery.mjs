import { spawn } from 'node:child_process';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout as pause } from 'node:timers/promises';

const root = resolve(process.argv[2] || join(dirname(fileURLToPath(import.meta.url)), '..'));
const profile = await mkdtemp(join(tmpdir(), 'mavic-xhs-gallery-'));
const address = pathToFileURL(join(root, '打开看图.html')).href;
const edge = spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', [
  '--headless', '--disable-gpu', '--no-first-run', '--disable-extensions',
  '--disable-background-networking', '--remote-debugging-port=0',
  '--user-data-dir=' + profile, address,
], { windowsHide: true, stdio: 'ignore' });

let connection;
try {
  let port;
  for (let i = 0; i < 100 && !port; i++) {
    try {
      port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split(/\r?\n/)[0];
    } catch {
      await pause(100);
    }
  }
  const open = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
  const page = open.find(item => item.type === 'page' && item.url === address);
  connection = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((done, fail) => { connection.onopen = done; connection.onerror = fail; });
  let id = 0;
  const pending = new Map();
  connection.onmessage = event => {
    const result = JSON.parse(event.data);
    pending.get(result.id)?.(result);
    pending.delete(result.id);
  };
  const call = (method, params = {}) => new Promise(done => {
    pending.set(++id, done);
    connection.send(JSON.stringify({ id, method, params }));
  });
  const script = async expression => {
    const response = await call('Runtime.evaluate', { expression, returnByValue: true });
    if (response.error || response.result.exceptionDetails) throw Error(JSON.stringify(response));
    return response.result.result.value;
  };
  await call('Page.enable');
  for (const width of [1440, 390]) {
    await call('Emulation.setDeviceMetricsOverride', {
      width, height: 910, deviceScaleFactor: 1, mobile: width < 600,
    });
    await call('Page.reload', { ignoreCache: true });
    let images;
    for (let i = 0; i < 65; i++) {
      images = await script("[...document.images].map(img=>{img.loading='eager';return img.naturalWidth})");
      if (images.length === 19 && images.every(Boolean)) break;
      await pause(100);
    }
    const state = await script("({view:innerWidth, page:document.documentElement.scrollWidth, client:document.documentElement.clientWidth, cards:document.querySelectorAll('#post figure').length, columns:getComputedStyle(document.querySelector('#post .grid')).gridTemplateColumns.split(' ').length})");
    if (images.length !== 19 || !images.every(Boolean) || state.cards !== 10 ||
        state.view !== width || state.page !== state.client || state.columns !== (width < 600 ? 1 : 5)) {
      throw Error(JSON.stringify({ state, images }));
    }
    console.log(JSON.stringify({ ...state, decodedThumbnails: images.length }));
  }
  await Promise.race([call('Browser.close'), pause(700)]);
} finally {
  connection?.close();
  if (edge.exitCode === null) edge.kill();
}
