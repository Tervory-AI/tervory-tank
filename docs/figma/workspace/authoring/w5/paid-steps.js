// Proposed founder paid-step settings. Illustrative dynamic rows; no runtime paid policy changes.
const mobile=__MOBILE__, states=__STATES__;
const page=await figma.getNodeByIdAsync('514:3092');await figma.setCurrentPageAsync(page);
const source=await figma.getNodeByIdAsync(mobile?'514:3802':'514:3163');
const fonts=new Map();for(const t of source.findAllWithCriteria({types:['TEXT']}))for(const s of t.getStyledTextSegments(['fontName']))fonts.set(JSON.stringify(s.fontName),s.fontName);
for(const f of fonts.values())await figma.loadFontAsync(f);for(const style of ['Regular','Semi Bold','Medium'])await figma.loadFontAsync({family:'Inter',style});
const vars={};for(const [k,id] of Object.entries({navy:'42:14',white:'42:13',canvas:'42:12',border:'465:26692',s8:'42:23',s16:'42:24',s24:'42:25',r8:'42:31'}))vars[k]=await figma.variables.getVariableByIdAsync('VariableID:'+id);
const rgb={navy:{r:0,g:24/255,b:64/255},white:{r:1,g:1,b:1},canvas:{r:244/255,g:246/255,b:251/255},border:{r:132/255,g:141/255,b:163/255}};
const paint=k=>figma.variables.setBoundVariableForPaint({type:'SOLID',color:rgb[k]},'color',vars[k]);
const primary=await figma.getNodeByIdAsync('266:3032'),secondary=await figma.getNodeByIdAsync('266:3034'),field=await figma.getNodeByIdAsync('93:6');
function box(parent,name,w,pad=0,gap=16){const n=figma.createAutoLayout('VERTICAL');n.name=name;n.resize(w,10);n.primaryAxisSizingMode='AUTO';n.counterAxisSizingMode='FIXED';n.fills=[];n.itemSpacing=gap;if(vars['s'+gap])n.setBoundVariable('itemSpacing',vars['s'+gap]);for(const p of ['paddingTop','paddingBottom','paddingLeft','paddingRight']){n[p]=pad;if(vars['s'+pad])n.setBoundVariable(p,vars['s'+pad]);}parent.appendChild(n);return n;}
function text(parent,value,size=14,bold=false){const t=figma.createText();t.name=value;t.fontName={family:'Inter',style:bold?'Semi Bold':'Regular'};t.fontSize=size;t.lineHeight={unit:'PIXELS',value:Math.ceil(size*1.4)};t.fills=[paint('navy')];t.characters=value;parent.appendChild(t);t.textAutoResize='HEIGHT';t.resize(parent.width-parent.paddingLeft-parent.paddingRight,Math.max(20,t.height));t.layoutSizingHorizontal='FILL';return t;}
function button(parent,label,main=false){const src=main?primary:secondary,n=src.createInstance();const owner=src.parent.type==='COMPONENT_SET'?src.parent:src;const key=Object.keys(owner.componentPropertyDefinitions).find(k=>k.startsWith('Label#'));n.setProperties({[key]:label});n.name='Action / '+label;parent.appendChild(n);n.resize(Math.min(280,parent.width-parent.paddingLeft-parent.paddingRight),48);n.fills=[paint(main?'navy':'white')];if(!main){n.strokes=[paint('navy')];n.strokeWeight=1;}n.cornerRadius=8;n.setBoundVariable('cornerRadius',vars.r8);for(const t of n.findAllWithCriteria({types:['TEXT']})){t.fontName={family:'Inter',style:'Semi Bold'};t.fills=[paint(main?'white':'navy')];}return n;}
function card(parent,title){const n=box(parent,title,parent.width-parent.paddingLeft-parent.paddingRight,16);n.fills=[paint('white')];n.strokes=[paint('border')];n.strokeWeight=1;n.cornerRadius=8;n.setBoundVariable('cornerRadius',vars.r8);if(title)text(n,title,20,true);return n;}
async function wire(n,to){await n.setReactionsAsync([{trigger:{type:'ON_CLICK'},actions:[{type:'NODE',destinationId:to,navigation:'NAVIGATE',transition:null,preserveScrollPosition:false}]}]);}
const frames=[],created=[],links=[];let x=Math.max(...page.children.map(n=>n.x+n.width))+160;
const samples=[{task:'[Task A]',steps:[['[Paid step 1]','Auto'],['[Paid step 2]','Ask'],['[Paid step 3]','Auto']]},{task:'[Task B]',steps:[['[Paid step 1]','Ask'],['[Paid step 2]','Auto']]}];
for(const state of states){
 const name='Paid steps settings / '+state+' / '+(mobile?'375':'1440')+' · Proposed';if(page.children.some(n=>n.name===name))throw Error('Already exists '+name);
 const root=source.clone();page.appendChild(root);root.name=name;root.x=x;root.y=1200;x+=(mobile?535:1600);const body=root.children[1];for(const n of [...body.children])n.remove();body.itemSpacing=16;body.setBoundVariable('itemSpacing',vars.s16);body.clipsContent=true;body.overflowDirection='VERTICAL';
 text(body,'Proposed · Illustrative paid-step inventory',12,true);text(body,'Paid steps settings',mobile?28:32,true);text(body,'Founder only',14,true);
 let pause=null,save=null,retry=null;const controls=[];
 if(['Empty','Loading','Error'].includes(state)){
  const panel=card(body,state==='Empty'?'No paid steps yet.':state==='Loading'?'Loading…':'Something went wrong');
  if(state==='Empty')text(panel,'Free steps stay automatic.');if(state==='Loading')for(let i=0;i<3;i++){const s=box(panel,'Loading placeholder',panel.width-32,0);s.resize(panel.width-32,48);s.primaryAxisSizingMode='FIXED';s.fills=[paint('canvas')];}if(state==='Error')retry=button(panel,'Try again',true);
 }else{
  const global=card(body,state==='Paused'?'Paid work is paused.':'Paid work');text(global,'Ask / Auto is set separately for every paid step.');pause=button(global,state==='Paused'?'Resume paid work':'Pause all paid work',true);if(state==='Paused')text(global,'Ask / Auto settings are kept.');if(state==='Saved')text(global,'Settings saved.',18,true);
  text(body,'Free steps stay automatic.');
  const tasks=box(body,'Configured tasks',body.width-48,0,16);tasks.layoutMode=mobile?'VERTICAL':'HORIZONTAL';tasks.primaryAxisSizingMode=mobile?'AUTO':'FIXED';tasks.counterAxisSizingMode=mobile?'FIXED':'AUTO';
  for(const [taskIndex,task] of samples.entries()){
   const col=box(tasks,task.task,mobile?tasks.width:(tasks.width-16)/2,0,16);text(col,task.task,20,true);
   for(const [stepIndex,[label,mode]] of task.steps.entries()){
    const component=await figma.getNodeByIdAsync(mode==='Ask'?'514:3146':'514:3154');const row=component.createInstance();col.appendChild(row);row.name='Paid step / '+task.task+' / '+label;row.resize(col.width,row.height);row.primaryAxisSizingMode='AUTO';row.layoutSizingVertical='HUG';row.layoutSizingHorizontal='FILL';
    const values={Step:label,Details:'[Route name] · Cost per call: —'+(state==='Paused'?' · '+mode:'')};const props={};for(const [k,v] of Object.entries(values)){const p=Object.keys(row.componentProperties).find(p=>p.split('#')[0]===k);if(p)props[p]=v;}row.setProperties(props);
    for(const t of row.findAllWithCriteria({types:['TEXT']})){if(t.characters===label||t.characters.startsWith('[Route name]')){t.resize(col.width-32,t.height);t.textAutoResize='HEIGHT';t.layoutSizingHorizontal='FILL';}}
    const buttons=row.findAllWithCriteria({types:['INSTANCE']}).filter(i=>i.findAllWithCriteria({types:['TEXT']}).some(t=>['Ask','Auto'].includes(t.characters)));
    if(state==='Paused')for(const b of buttons){await b.setReactionsAsync([]);if(b.fills.some(p=>p.type==='SOLID'&&p.color.b<.5)){b.fills=[paint('canvas')];for(const t of b.findAllWithCriteria({types:['TEXT']}))t.fills=[paint('navy')];}}
    controls.push({task:task.task,taskIndex,step:label,stepIndex,mode,id:row.id,buttons:buttons.map(b=>({id:b.id,label:b.findAllWithCriteria({types:['TEXT']})[0].characters})),paused:state==='Paused'});
   }
  }
  save=button(body,'Save settings',true);
 }
 const needed=body.children.reduce((a,n)=>a+n.height,0)+body.itemSpacing*(body.children.length-1)+body.paddingTop+body.paddingBottom;root.resize(mobile?375:1440,Math.max(900,needed+(mobile?root.children[0].height:0)));if(!mobile)root.children[0].resize(240,root.height);
 for(const t of root.findAllWithCriteria({types:['TEXT']})){t.setBoundVariable('fontFamily',null);t.fontName={family:'Inter',style:t.fontName.style==='Semi Bold'?'Semi Bold':'Regular'};}
 const record={id:root.id,name,state,mobile,width:root.width,height:root.height,pause:pause?.id,save:save?.id,retry:retry?.id,controls};frames.push(record);created.push(root.id,...root.findAll(()=>true).map(n=>n.id));
}
const checks=[];for(const record of frames){const f=page.children.find(n=>n.id===record.id);record.screenshot='paid-steps-'+record.state.toLowerCase()+'-'+record.width+'.png';const texts=f.findAllWithCriteria({types:['TEXT']});checks.push({id:f.id,width:f.width,height:f.height,paidSteps:record.controls.length,askAutoPairs:record.controls.map(c=>({id:c.id,labels:c.buttons.map(b=>b.label)})),nonInter:texts.filter(t=>t.fontName.family!=='Inter').map(t=>t.id),textOverflow:texts.filter(t=>t.visible&&t.parent&&t.parent.type!=='PAGE'&&(t.x < -1||t.y < -1||t.x+t.width>t.parent.width+1||t.y+t.height>t.parent.height+1)).map(t=>({id:t.id,text:t.characters,parent:t.parent.id}))});figma.io.write(record.screenshot,await f.exportAsync({format:'PNG',constraint:{type:'SCALE',value:1}}));}
return{pageId:page.id,status:'Proposed',screen:'Paid steps',frames,checks,createdNodeIds:[...new Set(created)],copy:[...new Set(frames.flatMap(r=>page.children.find(n=>n.id===r.id).findAllWithCriteria({types:['TEXT']}).map(t=>t.characters)))]};
