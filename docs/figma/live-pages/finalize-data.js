// Preserve captured page geometry and wording; only repair browser-native conversion gaps.
const frames=[await figma.getNodeByIdAsync('604:9'),await figma.getNodeByIdAsync('606:9')];
let page=figma.root.children.find(p=>p.name==='15 · Live pages · Proposed');
const created=[],changed=[],removed=[];
if(!page){page=figma.createPage();page.name='15 · Live pages · Proposed';created.push(page.id);}
await figma.setCurrentPageAsync(page);
for(const style of ['Regular','Medium','Semi Bold'])await figma.loadFontAsync({family:'Inter',style});
await figma.loadFontAsync({family:'Arimo',style:'Regular'});
const primary=await figma.getNodeByIdAsync('266:3032');
for(const t of primary.findAllWithCriteria({types:['TEXT']}))for(const s of t.getStyledTextSegments(['fontName']))await figma.loadFontAsync(s.fontName);
for(const f of frames){
 page.appendChild(f);f.name='Data / '+f.width+' / As built / Proposed';f.x=f.width===1440?0:1520;f.y=0;changed.push(f.id);
 const file=f.findOne(n=>n.name==='File Upload');
 const t=figma.createText();t.fontName={family:'Arimo',style:'Regular'};t.fontSize=17;t.characters='Choose File';t.fills=[{type:'SOLID',color:{r:0,g:0,b:0}}];t.textAutoResize='WIDTH_AND_HEIGHT';
 const button=figma.createFrame();button.name='Native browser file selector';button.resize(t.width+16,26);button.fills=[{type:'SOLID',color:{r:.937,g:.937,b:.937}}];button.strokes=[{type:'SOLID',color:{r:.46,g:.46,b:.46}}];button.strokeWeight=1;button.cornerRadius=2;
 file.appendChild(button);if(file.layoutMode!=='NONE')button.layoutPositioning='ABSOLUTE';button.x=13;button.y=11;button.appendChild(t);t.x=8;t.y=2;
 const value=figma.createText();value.name='Native browser empty filename';value.fontName={family:'Inter',style:'Regular'};value.fontSize=17;value.characters='No file chosen';value.fills=[{type:'SOLID',color:{r:0,g:0,b:0}}];file.appendChild(value);if(file.layoutMode!=='NONE')value.layoutPositioning='ABSOLUTE';value.x=button.x+button.width+4;value.y=13;
 created.push(button.id,t.id,value.id);
 const check=f.findOne(n=>n.name==='Checkbox');check.fills=[];const blue=check.children[0];blue.resize(13,13);blue.y=15.5;const icon=blue.children[0];icon.y=1;changed.push(check.id,blue.id,icon.id);
 const wrap=f.findOne(n=>n.name==='Button'&&n.findOne(t=>t.type==='TEXT'&&t.characters==='Run Base')),old=wrap.children.find(n=>n.type==='TEXT');
 const type={fontName:old.fontName,fontSize:old.fontSize,lineHeight:old.lineHeight},fills=wrap.fills;removed.push(old.id);old.remove();
 const n=primary.createInstance();wrap.appendChild(n);if(wrap.layoutMode!=='NONE')n.layoutPositioning='ABSOLUTE';n.x=0;n.y=0;n.resize(wrap.width,wrap.height);
 const owner=primary.parent.type==='COMPONENT_SET'?primary.parent:primary,key=Object.keys(owner.componentPropertyDefinitions).find(k=>k.startsWith('Label#'));
 n.setProperties({[key]:'Run Base'});n.fills=fills;n.cornerRadius=10;n.paddingLeft=wrap.paddingLeft;n.paddingRight=wrap.paddingRight;n.paddingTop=wrap.paddingTop;n.paddingBottom=wrap.paddingBottom;
 for(const t of n.findAllWithCriteria({types:['TEXT']})){t.fontName=type.fontName;t.fontSize=type.fontSize;t.lineHeight=type.lineHeight;t.fills=[{type:'SOLID',color:{r:1,g:1,b:1}}];}
 wrap.fills=[];created.push(n.id,...n.findAll(()=>true).map(n=>n.id));changed.push(file.id,wrap.id);
}
for(const id of ['601:9','602:9']){const n=await figma.getNodeByIdAsync(id);if(n){removed.push(n.id,...n.findAll(()=>true).map(n=>n.id));n.remove();}}
return{fileUrl:'https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS',pageId:page.id,frames:frames.map(f=>({id:f.id,name:f.name,width:f.width,height:f.height,nodeIds:[f.id,...f.findAll(()=>true).map(n=>n.id)],copy:f.findAllWithCriteria({types:['TEXT']}).map(t=>t.characters)})),createdNodeIds:created,mutatedNodeIds:changed,removedNodeIds:removed};
