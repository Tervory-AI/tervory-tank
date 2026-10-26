"""Copy Workspace to a temporary cloud directory and stub Clerk there only."""
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
target = Path(tempfile.mkdtemp(prefix="base-local-fixture-")) / "workspace"
shutil.copytree(ROOT / "workspace", target, ignore=shutil.ignore_patterns("node_modules", ".next", "*.tsbuildinfo", ".env*"))
(target / "node_modules").symlink_to(ROOT / "workspace/node_modules", target_is_directory=True)
(target / "middleware.ts").write_text('import { NextResponse } from "next/server"; export function middleware() { return NextResponse.next(); }\n')
(target / "lib/tenant.ts").write_text('''export type Tenant = {tenantId: string; orgId: string; orgName: string; userId: string};
export async function currentTenant(): Promise<Tenant> { return {tenantId: "ba5e0000-0000-4000-8000-000000000111", orgId: "local-fixture", orgName: "Local fixture workspace", userId: "local-fixture-user"}; }
export const activeTenant = currentTenant;
''')
page = target / "app/base/page.tsx"
page.write_text(page.read_text().replace('import { auth } from "@clerk/nextjs/server";', 'async function auth() { return {userId: "local-fixture-user"}; }'))
(target / "app/layout.tsx").write_text('''import { inter, jost, mono } from "./fonts";
import "./globals.css";
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en" className={`${jost.variable} ${inter.variable} ${mono.variable}`}><body>
    <div style={{position:"fixed",top:0,right:0,zIndex:99999,background:"#fff",color:"#001840",border:"2px solid #001840",padding:"8px"}}>local, fixture page</div>
    <main>{children}</main></body></html>;
}
''')
print(target)
