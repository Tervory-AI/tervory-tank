import { redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import { triggerIdentity } from "@/lib/trigger";
import { deviceApproval, deviceCode, deviceRegion } from "@/lib/device-login";
import { decideDevice } from "./actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "Approve CLI sign-in", referrer: "no-referrer" };

type Params = Promise<Record<string, string | string[] | undefined>>;
const one = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
const REGION_LABEL = { "us-east": "US East", za: "South Africa (ZA)" } as const;
const RESULTS: Record<string, string> = {
  approved: "Approved. Return to your terminal; the CLI finishes signing in by itself.",
  denied: "Denied. The CLI was not signed in.",
  failed: "This code has expired, was already used, or could not be recorded. Run tervory login again.",
  invalid: "That request was not valid. Run tervory login again.",
};

/** The one CLI approval page: signed in with Clerk, shows the code, org and device. */
export default async function DeviceApprovalPage({ searchParams }: { searchParams: Params }) {
  const tenant = await triggerIdentity(await activeTenant());
  if (!tenant) redirect("/onboarding");
  const params = await searchParams;
  const result = one(params.result);
  if (result && RESULTS[result]) {
    return <main className="device-approval"><h1>Tervory CLI sign-in</h1><p role="status">{RESULTS[result]}</p></main>;
  }
  const code = deviceCode(one(params.code));
  const region = deviceRegion(one(params.region) ?? "us-east");
  if (!code || !region) {
    return <main className="device-approval"><h1>Tervory CLI sign-in</h1><p role="alert">{RESULTS.invalid}</p></main>;
  }
  const lookup = await deviceApproval(tenant, region, code);
  if (!lookup.ok) {
    return <main className="device-approval"><h1>Tervory CLI sign-in</h1><p role="alert">{lookup.message}</p></main>;
  }
  return (
    <main className="device-approval">
      <h1>Approve CLI sign-in?</h1>
      <p>Only approve if you just ran <code>tervory login</code> and your terminal shows this code.</p>
      <dl>
        <dt>Code</dt><dd><strong data-testid="device-code">{lookup.device.user_code}</strong></dd>
        <dt>Organization</dt><dd data-testid="device-org">{tenant.orgName}</dd>
        <dt>Device</dt><dd data-testid="device-name">{lookup.device.device_name}</dd>
        <dt>Region</dt><dd>{REGION_LABEL[lookup.device.region]}</dd>
      </dl>
      <form action={decideDevice}>
        <input type="hidden" name="code" value={lookup.device.user_code} />
        <input type="hidden" name="region" value={lookup.device.region} />
        <button type="submit" name="action" value="approve">Approve</button>{" "}
        <button type="submit" name="action" value="deny">Deny</button>
      </form>
      <p>The CLI gets a credential for this organization only. It expires and refreshes automatically; <code>tervory logout</code> revokes it.</p>
    </main>
  );
}
