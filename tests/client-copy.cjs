const assert=require('node:assert/strict');
const fs=require('node:fs');
const roster=[...fs.readFileSync('litellm/config.yaml','utf8').matchAll(/model_name:\s*["']?([^\s"'#]+)/g)].map(m=>m[1]);
const banned=['Skala','Tank','ledger','receipt IDs','haiku','sonnet','eval','gold','shadow','retire','rung','tenant','region box',...roster];
module.exports=text=>{for(const word of banned){const escaped=word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');assert(!new RegExp(`\\b${escaped}\\b`,'i').test(text),`banned client copy: ${word}`);}};
