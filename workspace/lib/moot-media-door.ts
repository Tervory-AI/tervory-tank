/** Read-only compatibility bridge to PR #791's authenticated shared Tank door.
 * Account clients, signing keys, upload writes and budgets belong to that door.
 * The legacy URL is a staged bridge, not a shared Moot/Zenas product identity.
 */
import { fetchWithDeadline } from './request';

const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ID=/^[0-9A-Za-z_-]{1,80}$/;
type Hearing={id:string;region:'us-east'|'za';phase:string;published:boolean};
type Row=Record<string,unknown>;
const object=(value:unknown):value is Row=>!!value&&typeof value==='object'&&!Array.isArray(value);
const fail=()=>new Error('media_unavailable');

export class TankMootMedia {
  constructor(private hearing:string,private region:'us-east'|'za',private current:()=>Promise<Hearing>){
    if(!UUID.test(hearing))throw fail();
  }
  private async read(kind:'uploads'|'assets'|'playback',id:string,publication=false):Promise<Row>{
    if(!ID.test(id))throw fail();
    const state=await this.current();
    if(state.id!==this.hearing||state.region!==this.region)throw fail();
    if(publication&&(state.phase!=='closed'||state.published!==true))throw fail();
    try{
      const response=await fetchWithDeadline(`/api/zenas/moot/hearings/${this.hearing}/media/${kind}/${id}`,{
        method:'GET',cache:'no-store',redirect:'error',credentials:'same-origin'});
      if(!response.ok)throw fail();
      const result:unknown=await response.json();if(!object(result))throw fail();
      return result;
    }catch{throw fail();}
  }
  async uploadStatus(id:string){
    const row=await this.read('uploads',id);
    if(row.upload_id!==id||typeof row.status!=='string'||row.playback_policy!=='signed')throw fail();
    return {upload_id:id,status:row.status,asset_id:typeof row.asset_id==='string'&&ID.test(row.asset_id)?row.asset_id:null};
  }
  async assetStatus(id:string){
    const row=await this.read('assets',id);
    if(row.asset_id!==id||typeof row.status!=='string')throw fail();
    return {asset_id:id,status:row.status,playback_ids:Array.isArray(row.playback_ids)?row.playback_ids.flatMap(p=>
      object(p)&&typeof p.id==='string'&&ID.test(p.id)&&p.policy==='signed'?[{id:p.id,policy:'signed' as const}]:[]):[]};
  }
  async playback(id:string){
    const row=await this.read('playback',id,true);
    if(row.playback_id!==id||row.playback_policy!=='signed'||typeof row.playback_url!=='string'||
      !Number.isSafeInteger(row.expires_in)||Number(row.expires_in)<=0)throw fail();
    let url:URL;try{url=new URL(row.playback_url);}catch{throw fail();}
    if(url.protocol!=='https:'||url.hostname!=='stream.mux.com'||url.pathname!==`/${id}.m3u8`||
      url.username||url.password||!url.searchParams.get('token'))throw fail();
    return {playback_url:url.toString(),expires_in:Number(row.expires_in),playback_policy:'signed' as const};
  }
}
