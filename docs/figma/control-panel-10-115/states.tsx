// Figma's own code for frame 20:44 "Control panel · states (approved 25 Oct)", exported 25 Oct 2026, 17:10 PT,
// with get_design_context, word for word. Measurement sheet only. Image: states.png.
// These are the only other texts the control panel may show. Each replaces its counterpart in frame 10:115:
//   22:25  replaces "Pause all paid work" (10:125) while paid work is paused
//   22:27  replaces "Pause workers" (22:22) while the squad workers are paused
//   20:52  replaces "Needs you" (10:243) when nothing needs the founder (no count shown)
export default function ControlPanelStatesApproved25Oct() {
  return (
    <div className="bg-[#f4f6fa] content-stretch flex flex-col gap-[24px] items-start p-[32px] relative size-full" data-node-id="20:44" data-name="Control panel · states (approved 25 Oct)">
      <div className="content-stretch flex gap-[16px] items-start overflow-clip relative shrink-0" data-node-id="22:24" data-name="Buttons · when paused">
        <div className="bg-[#e80008] content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[8px] shrink-0" data-node-id="22:25" data-name="Button: Resume paid work (shown while paid work is paused)">
          <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[14px] text-white whitespace-nowrap" data-node-id="22:26">Resume paid work</p>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex items-start overflow-clip px-[12px] py-[7px] relative rounded-[8px] shrink-0" data-node-id="22:27" data-name="Button: Resume workers (shown while workers are paused)">
          <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[13px] whitespace-nowrap" data-node-id="22:28">Resume workers</p>
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
