// Figma's own code for frame 7:221 "C5 · Agent page (Base)", page "2 · Client screens", exported 26 Oct 2026, 01:40 PT,
// with get_design_context, word for word. Measurement sheet only. Image: frame.png. Only change: the logo image points
// to the real file /brand/tervory-logo-reversed.png. Every DATA text (SPEC.md) is sample data and comes from a real source.
type SidebarNavItemProps = { className?: string; label?: string };

function SidebarNavItem({ className, label = "Dashboard" }: SidebarNavItemProps) {
  return (
    <div className={className || "content-stretch flex h-[40px] items-start px-[12px] py-[10px] relative rounded-[8px] w-[224px]"} data-node-id="2:12" data-name="Sidebar/Nav item">
      <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[15px] text-white whitespace-nowrap" data-node-id="2:13">{label}</p>
    </div>
  );
}

export default function C5AgentPageBase() {
  return (
    <div className="bg-[#f4f6fa] content-stretch flex items-start relative size-full" data-node-id="7:221" data-name="C5 · Agent page (Base): jobs, upload, ask Base · clean 26 Oct">
      <div className="bg-[#001840] content-stretch flex flex-col gap-[4px] h-full items-start overflow-clip pt-[20px] px-[16px] relative shrink-0 w-[256px]" data-node-id="7:222" data-name="Sidebar">
        <div className="content-stretch flex items-start overflow-clip pb-[12px] relative shrink-0" data-node-id="7:223" data-name="Logo · tervory-logo-reversed.png · 180 wide">
          <img alt="Tervory AI" className="block h-[33px] w-[180px] object-contain" data-node-id="26:30" src="/brand/tervory-logo-reversed.png" />
        </div>
        <div className="bg-white content-stretch flex items-start overflow-clip px-[12px] py-[10px] relative rounded-[10px] shrink-0 w-full" data-node-id="7:226" data-name="Account">
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[#001840] text-[13px] whitespace-nowrap" data-node-id="7:227">Northwind Law</p>
        </div>
        <SidebarNavItem className="content-stretch flex h-[40px] items-start px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" />
        <SidebarNavItem className="content-stretch flex h-[40px] items-start px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" label="Projects" />
        <SidebarNavItem className="content-stretch flex h-[40px] items-start px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" label="Chats" />
        <div className="bg-[#22345a] content-stretch flex h-[40px] items-start px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" data-node-id="7:234" data-name="Sidebar/Nav item">
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[15px] text-white whitespace-nowrap" data-node-id="I7:234;2:13">Squad</p>
        </div>
        <SidebarNavItem className="content-stretch flex h-[40px] items-start px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" label="Billing" />
        <SidebarNavItem className="content-stretch flex h-[40px] items-start px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" label="Settings" />
      </div>
      <div className="content-stretch flex flex-[1_0_0] flex-col gap-[20px] h-full items-start min-w-px overflow-clip px-[48px] py-[36px] relative" data-node-id="7:242" data-name="Main">
        <p className="[word-break:break-word] font-['Jost:Light'] font-light leading-[normal] relative shrink-0 text-[#001840] text-[34px] whitespace-nowrap" data-node-id="7:243">Base</p>
        <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] min-w-full not-italic relative shrink-0 text-[#3d4a66] text-[15px] w-[min-content]" data-node-id="7:244">Verified business lists.</p>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex gap-[10px] items-center overflow-clip pl-[16px] pr-[10px] py-[12px] relative rounded-[12px] shrink-0 w-full" data-node-id="7:245" data-name="Ask Base">
          <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#8c94a6] text-[15px]" data-node-id="7:246">Ask Base, or upload a list to verify…</p>
          <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[8px] shrink-0" data-node-id="7:247" data-name="Button: Upload list">
            <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[14px] whitespace-nowrap" data-node-id="7:248">Upload list</p>
          </div>
          <div className="bg-[#001840] content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[8px] shrink-0" data-node-id="7:249" data-name="Button: Ask">
            <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[14px] text-white whitespace-nowrap" data-node-id="7:250">Ask</p>
          </div>
        </div>
        <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[16px] whitespace-nowrap" data-node-id="7:251">Jobs</p>
        <div className="[word-break:break-word] bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col items-start leading-[normal] overflow-clip px-[20px] py-[8px] relative rounded-[12px] shrink-0 w-full" data-node-id="7:252" data-name="Table">
          <div className="content-stretch flex font-['Inter:Semi_Bold'] font-semibold gap-[12px] items-center not-italic overflow-clip py-[10px] relative shrink-0 text-[#3d4a66] text-[12px] w-full" data-node-id="7:253" data-name="Header row">
            <p className="flex-[1_0_0] min-w-px relative" data-node-id="7:254">Job</p>
            <p className="relative shrink-0 w-[130px]" data-node-id="7:255">Status</p>
            <p className="relative shrink-0 w-[80px]" data-node-id="7:256">Records</p>
            <p className="relative shrink-0 w-[80px]" data-node-id="7:257">Verified</p>
            <p className="relative shrink-0 w-[90px]" data-node-id="7:261">​</p>
          </div>
          {/* Rows, each: Job (Inter 13, flex-1) · Status (Inter, 130) · Records (JetBrains Mono, 80) · Verified (JetBrains Mono, 80) · "Download" (Inter, 90).
              7:262 "Delaware licence list" Done 1,284 1,051 · 7:271 "Texas licence list" Done 9,830 8,902 · 7:280 "Client list: Q3 dealers" Running 412 188 */}
          <div className="content-stretch flex font-normal gap-[12px] items-center overflow-clip py-[10px] relative shrink-0 text-[#001840] text-[13px] w-full" data-node-id="7:262" data-name="Row">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px not-italic relative" data-node-id="7:263">Delaware licence list</p>
            <p className="font-['Inter:Regular'] not-italic relative shrink-0 w-[130px]" data-node-id="7:264">Done</p>
            <p className="font-['JetBrains_Mono:Regular'] relative shrink-0 w-[80px]" data-node-id="7:265">1,284</p>
            <p className="font-['JetBrains_Mono:Regular'] relative shrink-0 w-[80px]" data-node-id="7:266">1,051</p>
            <p className="font-['Inter:Regular'] not-italic relative shrink-0 w-[90px]" data-node-id="7:270">Download</p>
          </div>
          <div className="content-stretch flex font-normal gap-[12px] items-center overflow-clip py-[10px] relative shrink-0 text-[#001840] text-[13px] w-full" data-node-id="7:271" data-name="Row">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px not-italic relative" data-node-id="7:272">Texas licence list</p>
            <p className="font-['Inter:Regular'] not-italic relative shrink-0 w-[130px]" data-node-id="7:273">Done</p>
            <p className="font-['JetBrains_Mono:Regular'] relative shrink-0 w-[80px]" data-node-id="7:274">9,830</p>
            <p className="font-['JetBrains_Mono:Regular'] relative shrink-0 w-[80px]" data-node-id="7:275">8,902</p>
            <p className="font-['Inter:Regular'] not-italic relative shrink-0 w-[90px]" data-node-id="7:279">Download</p>
          </div>
          <div className="content-stretch flex font-normal gap-[12px] items-center overflow-clip py-[10px] relative shrink-0 text-[#001840] text-[13px] w-full" data-node-id="7:280" data-name="Row">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px not-italic relative" data-node-id="7:281">Client list: Q3 dealers</p>
            <p className="font-['Inter:Regular'] not-italic relative shrink-0 w-[130px]" data-node-id="7:282">Running</p>
            <p className="font-['JetBrains_Mono:Regular'] relative shrink-0 w-[80px]" data-node-id="7:283">412</p>
            <p className="font-['JetBrains_Mono:Regular'] relative shrink-0 w-[80px]" data-node-id="7:284">188</p>
            <p className="font-['Inter:Regular'] not-italic relative shrink-0 w-[90px]" data-node-id="7:288">Download</p>
          </div>
        </div>
      </div>
    </div>
  );
}
