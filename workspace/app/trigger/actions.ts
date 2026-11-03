"use server";

import { auth } from "@clerk/nextjs/server";
import { activeTenant } from "@/lib/tenant";
import { commandRequest } from "@/lib/tank";

async function identity() {
 const tenant=await activeTenant();
 if (!tenant) throw new Error("This item is unavailable.");
 const {orgRole}=await auth();
 return {...tenant,tenantAdmin:orgRole==="org:admin"};
}
export async function readTrigger(path:string) {
 if (!/^(crm\/(leads|contacts|estimates|invoices)(\/[a-f0-9-]{36})?|marketing\/(channels|posts|composer|calendar|reviews)|bot\/(settings|inbox))(\?record_id=[a-f0-9-]{36})?$/.test(path)) throw new Error("This item is unavailable.");
 const actor=await identity();
 const result=await (await commandRequest(actor,`trigger/console/${path}`)).json();
 if(path==="bot/settings")result.settings={name:actor.orgName,...result.settings};
 return result;
}
export async function proposeTrigger(tool:string,arguments_:Record<string,unknown>) {
 return (await commandRequest(await identity(),"trigger/console/propose",{method:"POST",body:JSON.stringify({tool,arguments:arguments_})})).json();
}
export async function confirmTrigger(thread:string,card:string) {
 if (![thread,card].every(v=>/^[a-f0-9-]{36}$/.test(v))) throw new Error("This item is unavailable.");
 return (await commandRequest(await identity(),`cards/${card}`,{method:"POST",body:JSON.stringify({action:"confirm"})})).json();
}
