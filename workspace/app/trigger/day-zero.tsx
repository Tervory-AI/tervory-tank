import { Data } from "./copy";

export function FirstAction({area, section, data}: {area: string; section: string; data: Data}) {
  const list = (key: string) => Array.isArray(data[key]) ? (data[key] as unknown[]).length : null;
  let count: number | null = null;
  let action = "";
  if (area === "crm") {
    count = list("items");
    action = `Create your first ${section === "estimates" ? "estimate" : section === "invoices" ? "invoice" : section === "contacts" ? "contact" : "lead"} in Chats with Trigger CRM.`;
  } else if (area === "bot") {
    count = list(section === "settings" ? "sources" : "conversations");
    action = section === "settings" ? "Add an approved source in Chats to fill your catalogue, FAQs or documents." : "Add an approved source, then start a chat on your website.";
  } else if (section === "channels") {
    const connected = [data.gbp, data.facebook].some(row => row && typeof row === "object" && (row as Data).status === "connected");
    count = connected ? 1 : 0;
    action = "Connect Google Business Profile or Facebook to get started.";
  } else if (section === "reviews") {
    count = list("reviews");
    action = "Connect Google Business Profile and refresh reviews to fill this list.";
  } else {
    count = list("posts");
    action = "Create a draft in Composer, then approve and schedule it to fill your calendar and posts.";
  }
  return count === 0 || count === null ? <p className="trigger-first-action" role="status"><output>{count === 0 ? "0" : "—"}</output>{" · "}{action}</p> : null;
}
