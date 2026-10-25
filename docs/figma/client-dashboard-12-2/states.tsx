// Figma's own code for frame 20:2 "Client dashboard · states (approved 25 Oct)", exported 25 Oct 2026 with
// get_design_context, word for word. Measurement sheet only. Image: states.png.
// These are the only other texts the dashboard may show. Each replaces its counterpart in frame 12:2:
//   20:4 / 20:5 / 20:6  replace the greeting 12:19 (before 12:00, 12:00 to 17:59, from 18:00, the client's local time)
//   20:8   replaces "Waiting on you" (12:39) when nothing is waiting
//   20:21  replaces "Recent work" (12:51) when there is no work yet
//   20:40  replaces "Credits left" (12:35) when no credits have been bought
export default function ClientDashboardStatesApproved25Oct() {
  return (
    <div className="[word-break:break-word] bg-[#f4f6fa] content-stretch flex flex-col gap-[24px] items-start leading-[normal] p-[32px] relative size-full whitespace-nowrap" data-node-id="20:2" data-name="Client dashboard · states (approved 25 Oct)">
      <div className="content-stretch flex font-['Jost:Light'] font-light gap-[16px] items-start overflow-clip relative shrink-0 text-[#001840] text-[34px]" data-node-id="20:3" data-name="Greeting · by the client's local time">
        <p className="relative shrink-0" data-node-id="20:4">Good morning, Thandi</p>
        <p className="relative shrink-0" data-node-id="20:5">Good afternoon, Thandi</p>
        <p className="relative shrink-0" data-node-id="20:6">Good evening, Thandi</p>
      </div>
      <div className="content-stretch flex gap-[16px] items-start not-italic overflow-clip relative shrink-0" data-node-id="20:7" data-name="Empty states">
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col gap-[10px] items-start overflow-clip p-[22px] relative rounded-[16px] shrink-0 w-[538px]" data-node-id="20:8" data-name="Waiting on you · empty">
          <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[17px]" data-node-id="20:9">Waiting on you</p>
          <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[#3d4a66] text-[15px]" data-node-id="20:20">Nothing is waiting on you.</p>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col gap-[10px] items-start overflow-clip p-[22px] relative rounded-[16px] shrink-0 w-[538px]" data-node-id="20:21" data-name="Recent work · empty">
          <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[17px]" data-node-id="20:22">Recent work</p>
          <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[#3d4a66] text-[15px]" data-node-id="20:39">No work yet.</p>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col font-['Inter:Regular'] font-normal gap-[6px] items-start overflow-clip p-[22px] relative rounded-[16px] shrink-0 text-[#3d4a66] w-[353px]" data-node-id="20:40" data-name="Credits left · none bought">
          <p className="relative shrink-0 text-[14px]" data-node-id="20:41">Credits left</p>
          <p className="relative shrink-0 text-[15px]" data-node-id="20:43">No credits bought yet</p>
        </div>
      </div>
    </div>
  );
}
