// PR791's actual response shapes, optionally supplied by its FakeMuxProvider proof.
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
process.env.COMMAND_TEST_TOOLS=path.resolve('workspace/node_modules');
const {workspace}=require('../command_acceptance_20261031/workspace_loader.cjs');
const hearing='11111111-1111-4111-8111-111111111111';
const fixture=process.argv[2]?JSON.parse(fs.readFileSync(process.argv[2],'utf8')):{
 upload:{upload_id:'upload_fixture',status:'asset_created',asset_id:'asset_fixture',playback_policy:'signed'},
 asset:{asset_id:'asset_fixture',status:'ready',playback_ids:[{id:'playback_fixture',policy:'signed'}]},
 playback:{playback_id:'playback_fixture',playback_policy:'signed',playback_url:'https://stream.mux.com/playback_fixture.m3u8?token=placeholder',expires_in:3600}};
let state={id:hearing,region:'us-east',phase:'closed',published:true};const calls=[];
const load=workspace({env:{},fetch:async(url,init)=>{
 calls.push({url:String(url),method:init.method});
 const kind=String(url).split('/').at(-2);
 return Response.json({...({uploads:fixture.upload,assets:fixture.asset,playback:fixture.playback}[kind]),stream_key:'placeholder-private-stream-key'});
}});
const {TankMootMedia}=load('lib/moot-media-door.ts');const door=new TankMootMedia(hearing,'us-east',async()=>state);
(async()=>{
 const upload=await door.uploadStatus(fixture.upload.upload_id);assert.equal(upload.asset_id,fixture.asset.asset_id);assert(!JSON.stringify(upload).includes('upload_url'));
 const asset=await door.assetStatus(fixture.asset.asset_id);assert.equal(asset.status,'ready');
 const playback=await door.playback(fixture.playback.playback_id);assert.equal(playback.expires_in,fixture.playback.expires_in);
 assert(!JSON.stringify(playback).includes('stream_key'));assert(calls.every(c=>c.method==='GET'));
 assert(calls.every(c=>c.url.startsWith(`/api/zenas/moot/hearings/${hearing}/media/`)));
 const count=calls.length;state={...state,published:false};await assert.rejects(()=>door.playback(fixture.playback.playback_id),/media_unavailable/);assert.equal(calls.length,count);
 state={...state,region:'za'};await assert.rejects(()=>door.assetStatus(fixture.asset.asset_id),/media_unavailable/);assert.equal(calls.length,count);
 console.log('Shared Tank door: exact GET paths, status/playback shapes, publication/region gates and secret projection passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
