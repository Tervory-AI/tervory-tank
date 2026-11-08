/** Authenticated independent Moot media boundary. Legacy hearing APIs stay intact. */
import { auth, signinDirectory } from '@/lib/trigger-signin';
import { currentTenant } from '@/lib/tenant';
import { isWorkspaceOrigin } from '@/lib/workspace-origin';
import { tenantDestination } from '@/lib/tank';

export const runtime='nodejs';
export const dynamic='force-dynamic';
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SEATS=new Set(['applicant','respondent','judge']);
const reply=(body:unknown,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
type Context={params:Promise<{hearing:string}>};

async function serve(req:Request,context:Context){
  if(req.method==='POST'&&!isWorkspaceOrigin(req))return reply({error:'origin_required'},403);
  const hearing=(await context.params).hearing;
  if(!UUID.test(hearing))return reply({error:'not_found'},404);
  try{
    const identity=await auth();if(!identity.userId)return reply({error:'not_signed_in'},401);
    const tenant=await currentTenant();if(tenant.userId!==identity.userId)return reply({error:'not_found'},404);
    const directory=await signinDirectory();
    const membership=await directory.organizations.getOrganizationMembershipList({organizationId:tenant.orgId,userId:[tenant.userId],limit:1});
    if(!membership.data.some(row=>row.publicUserData?.userId===tenant.userId))return reply({error:'not_found'},404);
    const url=process.env.MOOT_RUNTIME_URL,key=process.env.MOOT_INTERNAL_API_KEY,region=process.env.MOOT_REGION;
    if(!url||!key||!['us-east','za'].includes(region??''))return reply({error:'media_unavailable'},503);
    const owner=await tenantDestination(tenant.tenantId);
    if(owner.home!==region)return reply({error:'wrong_region'},403);
    let seat=new URL(req.url).searchParams.get('seat');
    if(req.method==='POST'){
      const reader=req.body?.getReader();if(!reader)return reply({error:'invalid_request'},400);
      const chunks:Uint8Array[]=[];let size=0;
      while(true){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;if(size>1024){await reader.cancel();return reply({error:'invalid_request'},400);}chunks.push(next.value);}
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
      const body:unknown=JSON.parse(new TextDecoder().decode(bytes));
      if(!body||typeof body!=='object'||Array.isArray(body)||Object.keys(body).some(k=>k!=='seat'))return reply({error:'invalid_request'},400);
      seat=(body as {seat:string}).seat;
    }
    if(!seat||!SEATS.has(seat))return reply({error:'invalid_seat'},400);
    const params=new URLSearchParams({seat});
    const after=new URL(req.url).searchParams.get('after');
    if(after!==null){if(!/^\d{1,12}$/.test(after))return reply({error:'invalid_cursor'},400);params.set('after',after);}
    const target=new URL(`/internal/hearings/${hearing}/${req.method==='POST'?'grants':'resume'}`,url);
    if(req.method==='GET')target.search=params.toString();
    const response=await fetch(target,{method:req.method,headers:{'Content-Type':'application/json','X-Moot-Key':key,'X-Moot-Tenant':tenant.tenantId,'X-Moot-Actor':tenant.userId},
      ...(req.method==='POST'?{body:JSON.stringify({seat})}:{}),cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)});
    if(!response.ok)return reply({error:'media_unavailable'},response.status>=500?503:response.status);
    return reply(await response.json());
  }catch{return reply({error:'media_unavailable'},503);}
}
export const GET=serve;
export const POST=serve;
