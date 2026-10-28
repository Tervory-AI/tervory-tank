// Offline component harness. No sign-in or production file changes.
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '../..');
const { build } = require(process.env.RIG_ESBUILD_PATH || path.join(root, 'workspace/node_modules/esbuild'));
build({
  stdin: { contents: `import React from 'react'; import {createRoot} from 'react-dom/client';
    import {Lab} from './workspace/app/rig/lab';
    const root=createRoot(document.getElementById('root'));
    window.renderRig=(products=0,fits=0)=>root.render(<Lab accountName="Your account" products={products} fits={fits}
      plugins={{enabled:false,message:'',secrets:[],files:[],links:[],connections:[]}} />);
    window.renderRig();`, resolveDir: root, loader: 'tsx' },
  bundle: true, write: false, format: 'iife', jsx: 'automatic',
  nodePaths: [path.join(root, 'workspace/node_modules')],
  define: { 'process.env.NODE_ENV': '"production"' },
  plugins: [{ name: 'host-boundaries', setup(build) {
    build.onResolve({ filter: /^next\/navigation$/ }, () => ({ path: 'navigation', namespace: 'host' }));
    build.onResolve({ filter: /^\.\/plugins$/ }, args => args.importer.endsWith('/rig/lab.tsx') ? ({ path: 'plugins', namespace: 'host' }) : undefined);
    build.onLoad({ filter: /.*/, namespace: 'host' }, args => ({ contents: args.path === 'navigation'
      ? 'export const usePathname=()=>"/rig";' : 'export const Plugins=()=>null;' }));
  } }],
}).then(result=>fs.writeFileSync(process.argv[2], result.outputFiles[0].text)).catch(error=>{ console.error(error.message);process.exitCode=1; });
