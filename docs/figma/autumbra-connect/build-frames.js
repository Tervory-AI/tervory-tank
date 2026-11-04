// Run through Figma use_figma; creates only proposed M17 screens.
const provider = '__PROVIDER__';
const cf = provider === 'Cloudflare';
const pageName = '11 · Autumbra connect · M17 · Proposed';
const sources = await Promise.all(['231:11986','231:12014','231:11997','465:46179','231:12012','468:27711'].map(id=>figma.getNodeByIdAsync(id)));
const fonts = new Map();
for(const source of sources)for(const t of source.findAllWithCriteria({types:['TEXT']}))for(const seg of t.getStyledTextSegments(['fontName']))fonts.set(JSON.stringify(seg.fontName),seg.fontName);
for(const f of fonts.values())await figma.loadFontAsync(f);
await figma.loadFontAsync({family:'Inter',style:'Regular'});
await figma.loadFontAsync({family:'Inter',style:'Semi Bold'});
let page = figma.root.children.find(p=>p.name===pageName);
if(!page){page=figma.createPage();page.name=pageName;}
await figma.setCurrentPageAsync(page);
const existing=page.children.filter(n=>n.name.startsWith(`Autumbra / ${provider} /`));
if(existing.length)throw Error('Provider already exists; inspect before retrying');
const created=[];const frames=[];
const vars={};for(const [key,id] of Object.entries({surface:'42:13',ink:'42:14',muted:'42:15',canvas:'42:12',border:'465:26692',s8:'42:23',s16:'42:24',s24:'42:25',r8:'42:31'}))vars[key]=await figma.variables.getVariableByIdAsync('VariableID:'+id);
function paint(key){return figma.variables.setBoundVariableForPaint({type:'SOLID',color:({ink:{r:0,g:24/255,b:64/255},muted:{r:61/255,g:74/255,b:102/255},canvas:{r:244/255,g:246/255,b:250/255},border:{r:118/255,g:131/255,b:154/255},surface:{r:1,g:1,b:1}})[key]},'color',vars[key]);}
function bind(n,key,v){n.setBoundVariable(key,vars[v]);}
function stack(width,gap=16){const n=figma.createAutoLayout();n.layoutMode='VERTICAL';n.resize(width,10);n.primaryAxisSizingMode='AUTO';n.counterAxisSizingMode='FIXED';n.fills=[];bind(n,'itemSpacing',gap===8?'s8':gap===24?'s24':'s16');return n;}
function text(parent,words,size=14,bold=false){const n=figma.createText();n.name='Proposed wording / '+words;n.fontName={family:'Inter',style:bold?'Semi Bold':'Regular'};n.fontSize=size;n.lineHeight={unit:'PERCENT',value:145};n.fills=[paint('ink')];n.characters=words;parent.appendChild(n);n.textAutoResize='HEIGHT';n.resize(parent.width-(parent.paddingLeft||0)-(parent.paddingRight||0),n.height);n.layoutSizingHorizontal='FILL';return n;}
function action(parent,label,primary){const n=sources[primary?3:4].clone();n.name='CRM action / '+label;parent.appendChild(n);n.setProperties({'Label#93:0':label});n.resize(Math.min(280,parent.width-(parent.paddingLeft||0)-(parent.paddingRight||0)),48);n.layoutSizingHorizontal='FIXED';n.fills=[paint(primary?'ink':'surface')];for(const t of n.findAllWithCriteria({types:['TEXT']})){t.fills=[paint(primary?'surface':'ink')];t.textAlignHorizontal='CENTER';}return n;}
function field(parent,label,value){const n=sources[5].clone();parent.appendChild(n);n.name='Proposed field / '+label;n.setProperties({'Field#93:1':label,'Data#93:2':value});n.resize(parent.width-(parent.paddingLeft||0)-(parent.paddingRight||0),88);n.layoutSizingHorizontal='FILL';return n;}
const states=['Connect','Empty','Loading','Error','Connected','Disconnect','Disconnected'];
const baseX=cf?0:2200;
for(let i=0;i<states.length;i++)for(const mobile of [false,true]){
 const state=states[i],width=mobile?375:1440;
 const frame=sources[mobile?1:0].clone();page.appendChild(frame);frame.name=`Autumbra / ${provider} / ${state} / ${width} / Proposed`;frame.x=baseX+(mobile?1520:0);frame.y=i*1500;
 const notice=frame.children[0],viewport=frame.children[1],menu=viewport.children[0],content=viewport.children[1];
 notice.children[0].characters='Proposed · Not approved';
 if(menu.componentProperties['Product heading#508:0'])menu.setProperties({'Product heading#508:0':'Autumbra'});
 // Local instance typography override only; the shared component is untouched.
 for(const t of menu.findAllWithCriteria({types:['TEXT']})){t.setBoundVariable('fontFamily',null);t.fontName={family:'Inter',style:t.fontName.style==='Semi Bold'?'Semi Bold':'Regular'};}
 for(const c of [...content.children])c.remove();
 content.primaryAxisSizingMode='AUTO';content.itemSpacing=16;content.paddingTop=24;content.paddingBottom=24;content.paddingLeft=mobile?16:24;content.paddingRight=mobile?16:24;content.fills=[paint('canvas')];
 text(content,'Autumbra',14,true);text(content,'Connections',mobile?24:32,true);text(content,'Optional. You choose what to connect.');
 const card=sources[2].clone();content.appendChild(card);for(const c of [...card.children])c.remove();card.name=`MCP connection pattern / ${provider} / ${state}`;card.resize(content.width-content.paddingLeft-content.paddingRight,10);card.layoutSizingHorizontal='FILL';card.primaryAxisSizingMode='AUTO';card.counterAxisSizingMode='FIXED';card.itemSpacing=16;card.fills=[paint('surface')];card.strokes=[paint('border')];
 text(card,provider,20,true);
 text(card,'Proposed wording',14,true).fills=[paint('muted')];
 if(state==='Connect'){
   text(card,cf?'Connect Cloudflare':'Connect Google Workspace alerts',18,true);
   if(cf){field(card,'Website','[Website]');field(card,'Scoped API token','••••••••••••••••');text(card,'Permissions before saving',16,true);text(card,'Specific zone: [Website]');text(card,'Zone → Zone → Read');text(card,'Zone → WAF → Edit');text(card,'No DNS permission, account-wide scope, other zones, or global API key.');text(card,"Save this scoped API token to your client vault.");action(card,'Save and connect',true);}
   else{text(card,'Permissions before connecting',16,true);text(card,'Read Google Workspace security alerts.');text(card,'No email or file access.');text(card,'Autumbra reads alerts as they arrive and discards them.');action(card,'Sign in with the provider',true);}
   action(card,'Cancel',false);
 }else if(state==='Empty'){text(card,'No connections yet.');text(card,'Optional. You choose what to connect.');action(card,'Add connection',true);
 }else if(state==='Loading'){text(card,'Connecting…',16,true);text(card,cf?'Checking token permissions before saving.':'Waiting for Google Workspace authorization.');action(card,'Cancel',false);
 }else if(state==='Error'){text(card,'Connection failed',16,true);text(card,cf?'The token could not be verified. Nothing was saved.':'Google Workspace did not grant access to security alerts.');action(card,'Try again',true);action(card,'Cancel',false);
 }else if(state==='Connected'){text(card,'Connected',16,true);text(card,cf?'[Website]':'[Organization]');text(card,cf?'Scoped API token saved to your client vault.':'Google Workspace security alerts connected.');text(card,cf?'Permissions: Zone → Zone → Read; Zone → WAF → Edit.':'Permissions: read security alerts. No email or file access.');action(card,'Disconnect',false);
 }else if(state==='Disconnect'){text(card,`Disconnect ${provider}?`,18,true);text(card,cf?'Autumbra will stop using this connection. Its saved token will be removed from your client vault.':'Autumbra will stop receiving Google Workspace alerts through this connection.');action(card,'Disconnect',false);action(card,'Cancel',false);
 }else{text(card,'Disconnected',16,true);text(card,cf?'The saved token was removed from your client vault.':'Google Workspace alerts are disconnected.');action(card,'Add connection',true);}
 const requiredHeight=Math.max(mobile?900:900,content.height+(mobile?menu.height:0)+notice.height+24);frame.resize(width,requiredHeight);viewport.resize(width,requiredHeight-notice.height);if(!mobile)menu.resize(240,viewport.height);
 // Inter throughout these proposed screens, including reused field/action overrides.
 for(const t of frame.findAllWithCriteria({types:['TEXT']})){t.setBoundVariable('fontFamily',null);t.fontName={family:'Inter',style:t.fontName.style==='Semi Bold'?'Semi Bold':'Regular'};}
 created.push(frame.id,...frame.findAll(()=>true).map(n=>n.id));frames.push({id:frame.id,state,width,height:frame.height,name:frame.name,card:card.id,menu:menu.id});
}
return {pageId:page.id,frames,createdNodeIds:created};
