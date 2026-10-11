import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { lstat } from 'node:fs/promises';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { handleLaptop } from './laptopProvider.mjs';

export async function startPreview(port=8081,provider=null) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)),'../dist/chat-web');
  await lstat(resolve(root,'index.html'));
  const types = { '.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
    '.json':'application/json','.wasm':'application/wasm','.css':'text/css','.png':'image/png','.ico':'image/x-icon' };
  const server = createServer(async (request,response) => {
    response.setHeader('Cross-Origin-Opener-Policy','same-origin');
    response.setHeader('Cross-Origin-Embedder-Policy','require-corp');
    response.setHeader('Cache-Control','no-store');
    try {
      if(await handleLaptop(request,response,provider,'http://127.0.0.1:'+server.address().port)) return;
      if (!['GET','HEAD'].includes(request.method)) { response.writeHead(405); response.end(); return; }
      const pathname = decodeURIComponent(new URL(request.url,'http://127.0.0.1').pathname);
      const target = resolve(root,'.'+(pathname === '/' ? '/index.html' : pathname));
      if (!target.startsWith(root+sep)) { response.writeHead(403); response.end(); return; }
      const stat = await lstat(target);
      if (!stat.isFile() || stat.isSymbolicLink()) { response.writeHead(404); response.end(); return; }
      response.setHeader('Content-Type',types[extname(target)] ?? 'application/octet-stream');
      response.setHeader('Content-Length',stat.size);
      if (request.method === 'HEAD') response.end();
      else createReadStream(target).on('error',()=>response.destroy()).pipe(response);
    } catch { response.writeHead(404); response.end(); }
  });
  await new Promise((resolveReady,reject) => {
    server.once('error',reject); server.listen(port,'127.0.0.1',resolveReady);
  });
  const address = server.address();
  server.once('close',()=>provider?.close());
  return { server,url:'http://127.0.0.1:'+address.port };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.argv[2] ?? '8081');
  if (!Number.isSafeInteger(port) || port < 0 || port > 65535) throw new Error('Use a valid local port.');
  const { server,url } = await startPreview(port); console.log('Nook Expo web preview: '+url);
  const stop = () => server.close(()=>process.exit(0));
  process.once('SIGTERM',stop); process.once('SIGINT',stop);
}
