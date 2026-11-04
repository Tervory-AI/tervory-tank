// Persist layout positions after inserting slots in existing auto-layout frames.
await figma.setCurrentPageAsync(await figma.getNodeByIdAsync("513:37050"));
const ids=["566:395","566:601","566:799","566:2140","566:2249","566:2350"];
const roots=await Promise.all(ids.map(id=>figma.getNodeByIdAsync(id)));
const fonts=new Map();for(const root of roots)for(const t of root.findAllWithCriteria({types:["TEXT"]}))for(const s of t.getStyledTextSegments(["fontName"]))fonts.set(JSON.stringify(s.fontName),s.fontName);
await Promise.all([...fonts.values()].map(f=>figma.loadFontAsync(f)));
const mutatedNodeIds=[],frames=[];
for(const root of roots){
 const shell=root.children[1],body=shell.children[1],mobile=root.width===375;
 let y=body.paddingTop;
 for(const child of body.children){child.y=y;mutatedNodeIds.push(child.id);y+=child.height+body.itemSpacing;}
 const height=y-body.itemSpacing+body.paddingBottom;
 body.resize(body.width,height);body.layoutSizingVertical="HUG";
 const shellHeight=height+(mobile?shell.children[0].height:0);
 shell.resize(shell.width,shellHeight);shell.layoutSizingVertical="HUG";
 if(!mobile){shell.children[0].resize(240,shellHeight);shell.children[0].layoutSizingVertical="FILL";mutatedNodeIds.push(shell.children[0].id);}
 root.resize(root.width,shellHeight+root.children[0].height);root.layoutSizingVertical="HUG";
 mutatedNodeIds.push(root.id,shell.id,body.id);
 frames.push({id:root.id,width:root.width,height:root.height,bodyHeight:body.height,
  children:body.children.map(n=>({id:n.id,name:n.name,y:n.y,height:n.height})),
  overlaps:body.children.slice(1).filter((n,i)=>n.y<body.children[i].y+body.children[i].height).map(n=>n.id)});
}
return {mutatedNodeIds,frames};
