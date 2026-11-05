/* Bundle actual Workspace modules using Next's existing webpack and TypeScript. */
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),base=path.join(root,'workspace'),out=path.resolve(process.argv[2]);
fs.mkdirSync(out,{recursive:true});
const compiled=require(path.join(base,'node_modules/next/dist/compiled/webpack/webpack'));compiled.init();
const w=compiled.webpack;
const write=(name,source)=>{const p=path.join(out,name);fs.writeFileSync(p,source);return p;};
const nav=write('navigation.cjs','exports.usePathname=()=>location.pathname;');
const link=write('link.cjs',`const React=require('react');module.exports=function Link({children,...props}){return React.createElement('a',props,children)};`);
const clerk=write('clerk.cjs',`exports.OrganizationSwitcher=function(){return null;};`);
const action=write('actions.cjs','exports.pauseAction=async function(value){window.paidPauseCalls=(window.paidPauseCalls||[]).concat(value);return {};};');
const loader=write('typescript-loader.cjs',`const ts=require(${JSON.stringify(path.join(base,'node_modules/typescript'))});module.exports=function(source){return ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;};`);
const entry=write('entry.tsx',`import React from 'react';import {createRoot} from 'react-dom/client';import Shell from ${JSON.stringify(path.join(base,'app/trigger/shell'))};import {PaidSettings} from ${JSON.stringify(path.join(base,'app/settings/paid-steps/settings'))};createRoot(document.getElementById('root')).render(<Shell title="Workspace"><PaidSettings {...window.paidFixture}/></Shell>);`);
w({mode:'production',target:'web',entry,output:{path:out,filename:'bundle.js'},optimization:{minimize:false},
 resolve:{extensions:['.tsx','.ts','.js','.cjs'],modules:[path.join(base,'node_modules'),'node_modules'],alias:{'next/navigation$':nav,'next/link$':link,'@clerk/nextjs$':clerk,'../../control/actions$':action}},
 module:{rules:[{test:/\.tsx?$/,use:[loader]}]},plugins:[new w.DefinePlugin({'process.env.NODE_ENV':JSON.stringify('production')})]
},(error,stats)=>{if(error||stats.hasErrors()){console.error(error||stats.toString({all:false,errors:true}));process.exitCode=1;}});
