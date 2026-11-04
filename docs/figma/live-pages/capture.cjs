// Open the local capture URL through Chrome CDP; no account/session is loaded.
const fs=require('node:fs'),path=require('node:path');
const out=path.resolve(__dirname,'../../../.tmp/live-pages');
const [key,widthText,captureId]=process.argv.slice(2),width=Number(widthText);
(async()=>{
 const {port}=JSON.parse(fs.readFileSync(path.join(out,'server.json'),'utf8'));
 const info=await(await fetch('http://127.0.0.1:9330/json/version')).json();
 const socket=new WebSocket(info.webSocketDebuggerUrl),pending=new Map();let id=0;
 socket.onmessage=e=>{const r=JSON.parse(e.data);if(r.id&&pending.has(r.id)){const p=pending.get(r.id);pending.delete(r.id);r.error?p.reject(Error(r.error.message)):p.resolve(r.result);}};
 await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 function call(method,params={},sessionId){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});}
 const target=await call('Target.createTarget',{url:'about:blank'}),session=await call('Target.attachToTarget',{targetId:target.targetId,flatten:true});const sid=session.sessionId;
 const win=await call('Browser.getWindowForTarget',{targetId:target.targetId});await call('Browser.setWindowBounds',{windowId:win.windowId,bounds:{width,height:900}});
 await call('Page.enable',{},sid);await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sid);
 const endpoint='https://mcp.figma.com/mcp/capture/'+captureId+'/submit?bindVariables=true';
 const hash=captureId?'#figmacapture='+captureId+'&figmaendpoint='+encodeURIComponent(endpoint)+'&figmadelay=1500':'';
 await call('Page.navigate',{url:'http://127.0.0.1:'+port+'/'+key+(captureId?'':'?reference=1')+hash},sid);
 await new Promise(r=>setTimeout(r,2000));await call('Runtime.evaluate',{expression:'document.fonts.ready.then(()=>true)',awaitPromise:true,returnByValue:true},sid);
 const content=await call('Runtime.evaluate',{expression:'JSON.stringify({text:document.body.innerText,title:document.title,width:innerWidth,height:document.documentElement.scrollHeight,geometry:[...document.querySelectorAll("fieldset,legend,fieldset label,section .actions")].map(e=>({tag:e.tagName,text:e.innerText,rect:e.getBoundingClientRect().toJSON()})),controls:[...document.querySelectorAll("input[type=file],input[type=checkbox]")].map(e=>({type:e.type,rect:e.getBoundingClientRect().toJSON(),font:getComputedStyle(e).font,padding:getComputedStyle(e).padding,pseudoFont:getComputedStyle(e,"::file-selector-button").font,pseudoPadding:getComputedStyle(e,"::file-selector-button").padding})),fonts:[...new Set([...document.querySelectorAll("body *")].filter(e=>e.getClientRects().length).map(e=>getComputedStyle(e).fontFamily))]})',returnByValue:true},sid);
 const meta=JSON.parse(content.result.value);fs.writeFileSync(path.join(out,key+'-'+width+'.json'),JSON.stringify(meta,null,2));
 const image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height:Math.max(900,meta.height),scale:1}},sid);
 fs.writeFileSync(path.join(out,key+'-'+width+'.png'),Buffer.from(image.data,'base64'));
 console.log(JSON.stringify({key,width,height:meta.height,targetId:target.targetId,captureId:captureId||null}));if(captureId)await new Promise(r=>setTimeout(r,300000));socket.close();
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
