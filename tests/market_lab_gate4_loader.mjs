import { createRequire } from 'node:module';
const require = createRequire(new URL('../workspace/package.json', import.meta.url));
export { load } from './market_lab_h7_hooks.mjs';
import { resolve as base } from './market_lab_hooks.mjs';
export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'react' || specifier.startsWith('react/') || specifier.startsWith('react-dom')) return nextResolve(require.resolve(specifier), context);
  let code;
  if (specifier === 'next-auth/react') code = 'export const useSession=()=>({data:null,status:"unauthenticated"}); export const signOut=()=>{},signIn=()=>{}; export const SessionProvider=({children})=>children;';
  if (specifier === 'next/navigation') code = 'export const useRouter=()=>({refresh(){}}); export const usePathname=()=>"/market-lab"; export const redirect=()=>{throw Error("unexpected redirect")};';
  if (specifier.endsWith('/plugin-actions') || specifier === './plugin-actions') code = 'export const addLabConnection=()=>{},addLabLink=()=>{},removeLabConnection=()=>{},removeLabFile=()=>{},removeLabLink=()=>{},removeLabSecret=()=>{},saveLabKey=()=>{};';
  if (specifier.endsWith('/quarantine-actions') || specifier === './quarantine-actions') code = 'export const releaseBatch=()=>{},rejectBatch=()=>{},removeBatch=()=>{};';
  if (specifier === '@/lib/tenant') code = 'export const activeTenant=async()=>({tenantId:"00000000-0000-0000-0000-000000000031",userId:"placeholder-user"});';
  if (specifier.endsWith('.css')) code = 'export default {};';
  if (code) return {url: 'data:text/javascript,' + encodeURIComponent(code), shortCircuit:true};
  return base(specifier, context, nextResolve);
}
