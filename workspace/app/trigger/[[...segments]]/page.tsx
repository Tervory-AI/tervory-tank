import {notFound} from "next/navigation";
import {readTrigger} from "../actions";
import {CRM,Resource} from "../copy";
import CRMView from "../records";
import ConsoleView from "../view";
export const dynamic="force-dynamic";
export default async function Page({params}:{params:Promise<{segments?:string[]}>}) {
 const {segments:parts=["crm","leads"]}=await params;
 const [area,section,id]=parts;
 if(parts.length>3||id&&!/^[a-f0-9-]{36}$/.test(id))notFound();
 if(area==="crm"&&section in CRM){const resource=section as Resource;return <CRMView resource={resource} detail={!!id} data={await readTrigger(`crm/${resource}${id?`/${id}`:""}`)}/>;}
 if((area==="marketing"&&["channels","posts","composer","calendar","reviews"].includes(section))||(area==="bot"&&["inbox","settings"].includes(section)))return <ConsoleView area={area} section={section} id={id} data={await readTrigger(`${area}/${section}${id?`?record_id=${id}`:""}`)}/>;
 notFound();
}
