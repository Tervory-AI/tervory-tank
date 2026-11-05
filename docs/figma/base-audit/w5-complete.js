// Complete only the missing states; preserve all four existing frame IDs and their figures.
const mobile=__MOBILE__;
const page=await figma.getNodeByIdAsync('516:3152');await figma.setCurrentPageAsync(page);
const source=await figma.getNodeByIdAsync(mobile?'518:8746':'518:8159');
const fonts=new Map();for(const t of source.findAllWithCriteria({types:['TEXT']}))for(const s of t.getStyledTextSegments(['fontName']))fonts.set(JSON.stringify(s.fontName),s.fontName);for(const f of fonts.values())await figma.loadFontAsync(f);await figma.loadFontAsync({family:'Inter',style:'Semi Bold'});
const action=await figma.getNodeByIdAsync('266:3032');const frames=[],created=[];
for(const state of ['Loading','Error']){
 const name='Client case-study template / '+state+' / '+(mobile?375:1440)+' / Proposed';if(page.children.some(n=>n.name===name))throw Error('Already exists '+name);
 const f=source.clone();page.appendChild(f);f.name=name;f.x=mobile?5320:3800;f.y=state==='Loading'?48000:72000;
 const vp=f.children[1],content=vp.children[1],inner=content.children[0],notice=inner.children.find(t=>t.type==='TEXT'&&t.characters==='No work yet');notice.characters=state==='Loading'?'Loading… · Proposed':'Could not load the case study. Try again. · Proposed';let retry;
 const explain=notice.clone();inner.insertChild(inner.children.indexOf(notice)+1,explain);explain.characters=state==='Loading'?'Values are unavailable while loading. Zero charts are the template, not measured results. · Proposed':'Values are unavailable. Zero charts are the template, not measured results. · Proposed';explain.textAutoResize='HEIGHT';explain.resize(inner.width,explain.height);explain.layoutSizingHorizontal='FILL';
 if(state==='Error'){retry=action.createInstance();inner.insertChild(inner.children.indexOf(explain)+1,retry);const key=Object.keys(action.parent.componentPropertyDefinitions).find(k=>k.startsWith('Label#'));retry.setProperties({[key]:'Try again'});retry.resize(280,48);await retry.setReactionsAsync([{trigger:{type:'ON_CLICK'},actions:[{type:'NODE',destinationId:mobile?'518:7555':'518:6969',navigation:'NAVIGATE',transition:null}]}]);}
 const height=content.height+(mobile?vp.children[0].height:0)+f.children[0].height+24;f.resize(mobile?375:1440,height);vp.resize(f.width,height-f.children[0].height);if(!mobile)vp.children[0].resize(240,vp.height);
 const rec={id:f.id,state,width:f.width,height:f.height,name:f.name,retry:retry?.id,screenshot:'client-'+state.toLowerCase()+'-'+f.width+'.png'};frames.push(rec);created.push(f.id,...f.findAll(()=>true).map(n=>n.id));
}
return{frames,createdNodeIds:created,status:'Proposed'};
