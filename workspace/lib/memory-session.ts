import "server-only";
import { InputError } from "@/lib/route-input";

/** Refuse client-supplied tenant/user that disagree with the signed-in session. */
export function refuseClientImpersonation(
  session: { tenantId: string; userId: string },
  req: Request,
  body?: Record<string, unknown> | null,
): void {
  const url = new URL(req.url);
  const claims: Array<[string, string | null]> = [
    ["tenant_id", pick(body?.tenant_id, url.searchParams.get("tenant_id"), req.headers.get("x-tervory-tenant"))],
    ["user_id", pick(body?.user_id, body?.created_by, url.searchParams.get("user_id"), req.headers.get("x-tervory-user"))],
  ];
  for (const [label, claimed] of claims) {
    if (claimed == null || claimed === "") continue;
    const expected = label === "tenant_id" ? session.tenantId : session.userId;
    if (String(claimed) !== String(expected)) {
      throw new InputError(`impersonation refused: ${label} does not match signed-in caller`, 403);
    }
  }
}

function pick(...values: Array<unknown>): string | null {
  for (const value of values) {
    if (value == null || value === "") continue;
    return String(value);
  }
  return null;
}
