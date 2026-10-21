import { proofResponse } from "../server";
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams, format = params.get("format");
  if (format!=="csv" && format!=="pdf") return new Response("Not found",{status:404});
  const response = await proofResponse(Object.fromEntries(params),undefined,`/savings/export/${format}`);
  return new Response(response.body,{headers:{"Content-Type":format==="csv" ? "text/csv; charset=utf-8" : "application/pdf","Content-Disposition":`attachment; filename="client-savings.${format}"`,"Cache-Control":"no-store"}});
}
