// Market Lab frame slots — Proposed. Run in https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS
// Extends existing brief-detail frames; does not change shared mains or runtime code.
const page = await figma.getNodeByIdAsync("513:37050");
await figma.setCurrentPageAsync(page);
const targetIds = ["566:395", "566:601", "566:799", "566:2140", "566:2249", "566:2350"];
const targets = await Promise.all(targetIds.map(id => figma.getNodeByIdAsync(id)));
for (const frame of targets) {
  if (frame.findOne(n => n.name === "Confidence section · Proposed" || n.name === "History section · Proposed")) {
    throw Error("Slots already present: " + frame.id);
  }
}
const fontMap = new Map();
for (const frame of targets) for (const t of frame.findAllWithCriteria({types:["TEXT"]})) {
  for (const s of t.getStyledTextSegments(["fontName"])) fontMap.set(JSON.stringify(s.fontName), s.fontName);
}
await Promise.all([...fontMap.values()].map(f => figma.loadFontAsync(f)));
const [cardSource, headingSource, bodySource, actionSource, s8, s16, radius, stroke] = await Promise.all([
  figma.getNodeByIdAsync("566:569"), figma.getNodeByIdAsync("566:570"),
  figma.getNodeByIdAsync("566:571"), figma.getNodeByIdAsync("566:581"),
  figma.variables.getVariableByIdAsync("VariableID:42:23"),
  figma.variables.getVariableByIdAsync("VariableID:42:24"),
  figma.variables.getVariableByIdAsync("VariableID:42:31"),
  figma.variables.getVariableByIdAsync("VariableID:42:44")
]);
const before = targets.map(f => ({
  id:f.id, name:f.name, width:f.width, height:f.height,
  originals:[f,...f.findAll(()=>true)].map(n => ({
    id:n.id,name:n.name,type:n.type,
    ...n.type==="TEXT"?{characters:n.characters,fontName:n.fontName,fills:n.fills}:{},
    ...n.type==="INSTANCE"?{reactions:n.reactions}:{}
  }))
}));
const createdNodeIds = [], mutatedNodeIds = [];
const track = n => {createdNodeIds.push(n.id); return n;};
function text(parent, value, heading=false, propOwner=null, propName=null) {
  const n = track((heading?headingSource:bodySource).clone());
  parent.appendChild(n);
  n.name = propName || value;
  n.characters = value;
  n.textAutoResize = "HEIGHT";
  n.resize(Math.max(1,parent.width-parent.paddingLeft-parent.paddingRight-2),n.height);
  n.layoutSizingHorizontal = "FILL";
  n.layoutSizingVertical = "HUG";
  if (propOwner) {
    const key = propOwner.addComponentProperty(propName,"TEXT",value);
    n.componentPropertyReferences = {...n.componentPropertyReferences,characters:key};
    return {node:n,key};
  }
  return n;
}
function stack(parent,name,width,gap=s16) {
  const n=track(figma.createAutoLayout("VERTICAL"));
  n.name=name;n.resize(width,10);n.fills=[];
  n.primaryAxisSizingMode="AUTO";n.counterAxisSizingMode="FIXED";
  n.setBoundVariable("itemSpacing",gap);parent.appendChild(n);
  n.layoutSizingHorizontal="FILL";n.layoutSizingVertical="HUG";
  return n;
}
function cardMain(name) {
  const n=track(figma.createComponent());
  page.appendChild(n);n.name=name;n.x=23600;n.y=name.includes("Signal")?1700:2200;
  n.layoutMode="VERTICAL";n.resize(1072,10);n.primaryAxisSizingMode="AUTO";n.counterAxisSizingMode="FIXED";
  n.fills=cardSource.fills;n.strokes=cardSource.strokes;n.strokeWeight=cardSource.strokeWeight;
  n.strokeAlign=cardSource.strokeAlign;n.cornerRadius=cardSource.cornerRadius;
  for(const k of ["paddingLeft","paddingRight","paddingTop","paddingBottom","itemSpacing"])n.setBoundVariable(k,s16);
  n.setBoundVariable("cornerRadius",radius);n.setBoundVariable("strokeWeight",stroke);n.clipsContent=false;
  return n;
}
const signalMain=cardMain("H7 / Signal confidence · Proposed");
signalMain.description="Proposed original-signal card. Bind claim, confidence, kind, feed, frozen horizon, prediction reference and verified stored_href from one signals[] item. Unknown metrics remain an em dash. Source action stays disabled without a verified stored_href.";
const signalProps={};
for(const [key,value,heading] of [
  ["Signal","Signal 1",true],["Claim","[Claim 1]",false],
  ["Metrics","Confidence: 75.0% · Frozen horizon: 30 days",false],
  ["Pair","Warning pair / feed: [Warning pair] / [Feed]",false],
  ["Prediction","Prediction: [Saved prediction reference]",false]
]) signalProps[key]=text(signalMain,value,heading,signalMain,key).key;
const sourceButton=actionSource.clone();signalMain.appendChild(sourceButton);
createdNodeIds.push(sourceButton.id,...sourceButton.findAll(()=>true).map(n=>n.id));
sourceButton.name="Open stored source · unavailable placeholder";sourceButton.resize(280,48);
await sourceButton.setReactionsAsync([]);
const eventMain=cardMain("H7 / Recorded history event · Proposed");
eventMain.description="Proposed saved report or recorded delivery event. Bind happened_at and the event's own channel/status/reason. Never infer delivery history from current deliveries[].";
const eventProps={};
for(const [key,value,heading] of [
  ["Event","Email · [Recorded status]",true],["Time","Date: [Recorded date and time]",false],
  ["Reason","Reason: [Recorded reason, when present]",false]
])eventProps[key]=text(eventMain,value,heading,eventMain,key).key;
const reasonNode=eventMain.children.find(n=>n.name==="Reason");
eventProps.ShowReason=eventMain.addComponentProperty("Show reason","BOOLEAN",true);
reasonNode.componentPropertyReferences={...reasonNode.componentPropertyReferences,visible:eventProps.ShowReason};
function instance(parent,main,props,name) {
  const n=main.createInstance();parent.appendChild(n);n.name=name;n.setProperties(props);
  n.resize(parent.width,main.height);n.layoutSizingHorizontal="FILL";n.layoutSizingVertical="HUG";
  createdNodeIds.push(n.id,...n.findAll(()=>true).map(n=>n.id));return n;
}
const results=[];
for(const frame of targets) {
  const shell=frame.children[1],body=shell.children[1],reportIndex=Number(frame.name.match(/Report (\d)/)[1]);
  const count=reportIndex===2?2:3, width=frame.width===375?327:1072;
  const originalTextCount=frame.findAllWithCriteria({types:["TEXT"]}).length;
  const confidence=stack(body,"Confidence section · Proposed",width);
  text(confidence,"Confidence",true);
  text(confidence,"Original signal confidence. Unknown values stay —.");
  for(let i=1;i<=count;i++)instance(confidence,signalMain,{
    [signalProps.Signal]:"Signal "+i,
    [signalProps.Claim]:"[Claim "+i+"]",
    [signalProps.Metrics]:"Confidence: "+(reportIndex===1&&i===1?"75.0%":"—")+" · Frozen horizon: "+(reportIndex===1&&i===1?"30 days":"—"),
    [signalProps.Pair]:"Warning pair / feed: [Warning pair] / [Feed]",
    [signalProps.Prediction]:"Prediction: "+(reportIndex===1&&i===1?"[Saved prediction reference]":"—")
  },"Signal "+i+" · original confidence");
  const sourceIndex=body.children.findIndex(n=>n.type==="TEXT"&&n.characters.endsWith(" · Sources cited"));
  body.insertChild(sourceIndex,confidence);
  const history=stack(body,"History section · Proposed",width);
  text(history,"History",true);
  text(history,"Only recorded events are shown. Earlier sends are not reconstructed.");
  const date=["1 Nov 2026","1 Oct 2026","1 Sep 2026"][reportIndex-1];
  instance(history,eventMain,{
    [eventProps.Event]:"Saved report",[eventProps.Time]:"Date: "+date,[eventProps.Reason]:"",
    [eventProps.ShowReason]:false
  },"Saved report event · made_at");
  if(reportIndex===2) {
    text(history,"No recorded delivery events.");
  } else {
    for(const channel of ["Email","Webhook"])instance(history,eventMain,{
      [eventProps.Event]:channel+" · [Recorded status]",
      [eventProps.Time]:"Date: [Recorded date and time]",
      [eventProps.Reason]:"Reason: [Recorded reason, when present]",
      [eventProps.ShowReason]:true
    },channel+" · recorded history placeholder");
  }
  const backIndex=body.children.findIndex(n=>n.name==="Action / Monthly briefs");
  body.insertChild(backIndex,history);
  // Existing auto-layout propagates the added content; the desktop sidebar fills the shell.
  if(frame.width===1440){shell.children[0].layoutSizingVertical="FILL";mutatedNodeIds.push(shell.children[0].id);}
  mutatedNodeIds.push(frame.id,shell.id,body.id);
  const all=frame.findAll(()=>true),types={},images=[],fonts=new Set(),overflows=[];
  for(const n of all){
    types[n.type]=(types[n.type]||0)+1;
    if("fills"in n&&Array.isArray(n.fills)&&n.fills.some(p=>p.type==="IMAGE"))images.push({id:n.id,name:n.name,type:n.type,width:n.width,height:n.height});
    if(n.type==="TEXT")for(const s of n.getStyledTextSegments(["fontName"]))fonts.add(s.fontName.family);
  }
  for(const section of [confidence,history])for(const n of section.findAll(()=>true)){
    if(!n.visible)continue;
    if(n.x < -1||n.y < -1||n.x+n.width>n.parent.width+1||n.y+n.height>n.parent.height+1)overflows.push({id:n.id,name:n.name,parent:n.parent.id});
  }
  results.push({id:frame.id,name:frame.name,width:frame.width,height:frame.height,
    confidenceId:confidence.id,historyId:history.id,signalCount:count,historyEventCount:reportIndex===2?1:3,
    originalTextCount,descendantCount:all.length,types,images,fonts:[...fonts],newContentOverflows:overflows,
    sections:[confidence,history].map(n=>({id:n.id,x:n.x,y:n.y,width:n.width,height:n.height})),
    newCopy:[...new Set([confidence,history].flatMap(n=>n.findAllWithCriteria({types:["TEXT"]}).filter(t=>t.visible).map(t=>t.characters)))]
  });
}
const retained=before.map(b=>{
  const f=targets.find(n=>n.id===b.id),byId=new Map([f,...f.findAll(()=>true)].map(n=>[n.id,n]));
  return {id:b.id,removedOriginalIds:b.originals.filter(n=>!byId.has(n.id)).map(n=>n.id),
    changedOriginalText:b.originals.filter(n=>n.type==="TEXT"&&byId.get(n.id)?.characters!==n.characters).map(n=>n.id)};
});
return {status:"Proposed",fileUrl:"https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS",
  sourceBranch:"codex/market-lab-h7",sourceCommit:"1e6ef3af8334aef18ed1a7245ba1ac724a590ff5",
  baseline:before.map(b=>({id:b.id,name:b.name,width:b.width,height:b.height,originalNodeCount:b.originals.length,originalTextCount:b.originals.filter(n=>n.type==="TEXT").length})),frames:results,retained,createdNodeIds,mutatedNodeIds,
  components:[{id:signalMain.id,name:signalMain.name,properties:signalProps},{id:eventMain.id,name:eventMain.name,properties:eventProps}]};
