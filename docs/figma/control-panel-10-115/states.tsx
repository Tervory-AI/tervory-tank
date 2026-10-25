// Figma's own code for frame 20:44 "Control panel · states (approved 25 Oct)", exported 25 Oct 2026 with
// get_design_context, word for word. Measurement sheet only. Image: states.png.
// These are the only other texts the control panel may show. Each replaces its counterpart in frame 10:115:
//   20:46  replaces the health pill (10:122) when exactly 1 problem is open
//   20:49  replaces it when 2 or more are open: "N problems · Autumbra on watch", N = the real count
//   20:52  replaces "Needs you" (10:243) when nothing needs the founder (no count shown)
const imgStatusDot = "./assets/status-dot-red.svg";

export default function ControlPanelStatesApproved25Oct() {
  return (
    <div className="bg-[#f4f6fa] content-stretch flex flex-col gap-[24px] items-start p-[32px] relative size-full" data-node-id="20:44" data-name="Control panel · states (approved 25 Oct)">
      <div className="content-stretch flex gap-[16px] items-start overflow-clip relative shrink-0" data-node-id="20:45" data-name="Health · when something is down">
        <div className="bg-[#fdecec] content-stretch flex gap-[8px] items-center overflow-clip px-[14px] py-[8px] relative rounded-[999px] shrink-0" data-node-id="20:46" data-name="Health · 1 problem">
          <div className="relative shrink-0 size-[10px]" data-node-id="20:47" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[#e80008] text-[13px] whitespace-nowrap" data-node-id="20:48">1 problem · Autumbra on watch</p>
        </div>
        <div className="bg-[#fdecec] content-stretch flex gap-[8px] items-center overflow-clip px-[14px] py-[8px] relative rounded-[999px] shrink-0" data-node-id="20:49" data-name="Health · 2 or more problems (N problems)">
          <div className="relative shrink-0 size-[10px]" data-node-id="20:50" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[#e80008] text-[13px] whitespace-nowrap" data-node-id="20:51">2 problems · Autumbra on watch</p>
        </div>
      </div>
      <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col gap-[12px] items-start overflow-clip p-[20px] relative rounded-[14px] shrink-0 w-[520px]" data-node-id="20:52" data-name="Needs you · empty">
        <div className="content-stretch flex items-start overflow-clip relative shrink-0 w-full" data-node-id="20:53" data-name="Head">
          <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[16px] whitespace-nowrap" data-node-id="20:54">Needs you</p>
          <div className="flex-[1_0_0] h-px min-w-px relative" data-node-id="20:55" data-name="spacer" />
        </div>
        <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[13px] whitespace-nowrap" data-node-id="20:83">Nothing needs you.</p>
      </div>
    </div>
  );
}
