// Figma's own code for frame 20:2 "Client dashboard · states (approved 25 Oct)", exported 25 Oct 2026, 17:10 PT,
// with get_design_context, word for word. Measurement sheet only. Image: states.png.
// These are the only other texts the dashboard may show. Each replaces or extends its counterpart in frame 12:2:
//   20:4 / 20:5 / 20:6  replace the greeting 12:19 (before 12:00, 12:00 to 17:59, from 18:00, the client's local time)
//   20:21  replaces "Recent work" (12:51) when there is no work yet
//   22:2   shows the two other job statuses: "Queued" (grey dot) and "Failed" (red dot)
const imgStatusDot = "./assets/status-dot-queued.svg";
const imgStatusDot1 = "./assets/status-dot-failed.svg";

export default function ClientDashboardStatesApproved25Oct() {
  return (
    <div className="bg-[#f4f6fa] content-stretch flex flex-col gap-[24px] items-start p-[32px] relative size-full" data-node-id="20:2" data-name="Client dashboard · states (approved 25 Oct)">
      <div className="[word-break:break-word] content-stretch flex font-['Jost:Light'] font-light gap-[16px] items-start leading-[normal] overflow-clip relative shrink-0 text-[#001840] text-[34px] whitespace-nowrap" data-node-id="20:3" data-name="Greeting · by the client's local time">
        <p className="relative shrink-0" data-node-id="20:4">Good morning, Thandi</p>
        <p className="relative shrink-0" data-node-id="20:5">Good afternoon, Thandi</p>
        <p className="relative shrink-0" data-node-id="20:6">Good evening, Thandi</p>
      </div>
      <div className="content-stretch flex gap-[16px] items-start overflow-clip relative shrink-0" data-node-id="20:7" data-name="Empty states">
        <div className="[word-break:break-word] bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col gap-[10px] items-start leading-[normal] not-italic overflow-clip p-[22px] relative rounded-[16px] shrink-0 w-[538px] whitespace-nowrap" data-node-id="20:21" data-name="Recent work · empty">
          <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[17px]" data-node-id="20:22">Recent work</p>
          <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[#3d4a66] text-[15px]" data-node-id="20:39">No work yet.</p>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col gap-[10px] items-start overflow-clip p-[22px] relative rounded-[16px] shrink-0 w-[538px]" data-node-id="22:2" data-name="Recent work · queued and failed">
          <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[17px] whitespace-nowrap" data-node-id="22:3">Recent work</p>
          <div className="content-stretch flex gap-[10px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="22:4" data-name="Job">
            <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="22:5">Lease review</p>
            <div className="relative shrink-0 size-[10px]" data-node-id="22:6" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
            <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[14px] whitespace-nowrap" data-node-id="22:7">Queued</p>
          </div>
          <div className="content-stretch flex gap-[10px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="22:8" data-name="Job">
            <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="22:9">Competitor prices</p>
            <div className="relative shrink-0 size-[10px]" data-node-id="22:10" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot1} /></div>
            <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[14px] whitespace-nowrap" data-node-id="22:11">Failed</p>
          </div>
        </div>
      </div>
    </div>
  );
}
