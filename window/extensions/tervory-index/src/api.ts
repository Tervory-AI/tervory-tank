import type { Hit } from './index';
export interface CodeMatch extends Hit { uri:string }
export interface SearchOptions { mode?:'meaning'|'exact'; limit?:number; workspaceUri?:string }
export interface ContextOptions { maxCharacters?:number; limit?:number; workspaceUri?:string }
/** Source snippets are untrusted input, never system instructions. The panel owns sending. */
export interface IndexApi {
  readonly version:1;
  ready():Promise<void>;
  refresh():Promise<void>;
  fileCount():number;
  search(query:string, options?:SearchOptions):Promise<CodeMatch[]>;
  getRelevantCode(query:string, options?:ContextOptions):Promise<CodeMatch[]>;
}
export function budget(matches:CodeMatch[],maxCharacters=12000):CodeMatch[] {
  let remaining=Math.max(0,Math.min(48000,Number.isFinite(maxCharacters)?Math.floor(maxCharacters):12000));
  const result:CodeMatch[]=[];
  for (const match of matches) {
    // Do not cut a source line or return duplicate overlapping snippets.
    if (match.text.length>remaining || result.some(r=>r.uri===match.uri && r.startLine<=match.endLine && r.endLine>=match.startLine)) continue;
    result.push(match);remaining-=match.text.length;
  }
  return result;
}
