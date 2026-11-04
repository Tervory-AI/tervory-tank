// Parameters are capture frames already created from the unchanged local production render.
const specs=__FRAMES__;
const page=await figma.getNodeByIdAsync('610:675');await figma.setCurrentPageAsync(page);
const changed=[],frames=[];
for(const spec of specs){
 const f=await figma.getNodeByIdAsync(spec.id);if(f.width!==spec.width)throw Error('Capture width mismatch: '+f.id);
 page.appendChild(f);f.name=spec.title+' / '+spec.width+' / As built / Proposed';f.x=spec.width===1440?0:1520;f.y=spec.y;changed.push(f.id);
 for(const t of f.findAllWithCriteria({types:['TEXT']})){
  const link=t.hyperlink;
  if(link&&link!==figma.mixed&&link.type==='URL'&&/^https?:\/\/(localhost|127\.0\.0\.1):\d+/.test(link.value)){
   for(const s of t.getStyledTextSegments(['fontName']))await figma.loadFontAsync(s.fontName);
   t.hyperlink={type:'URL',value:link.value.replace(/^https?:\/\/(localhost|127\.0\.0\.1):\d+/,spec.origin)};changed.push(t.id);
  }
 }
 frames.push({id:f.id,name:f.name,width:f.width,height:f.height,copy:f.findAllWithCriteria({types:['TEXT']}).map(t=>({id:t.id,text:t.characters})),nodeIds:[f.id,...f.findAll(()=>true).map(n=>n.id)]});
}
return{fileUrl:'https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS',pageId:page.id,frames,mutatedNodeIds:changed,createdNodeIds:frames.flatMap(f=>f.nodeIds)};
