// Figma's own code for frame 26:31 "C5 · states (approved 26 Oct)", exported 26 Oct 2026, 01:40 PT, word for word.
// The only other texts the Base page may show:
//   26:32  replaces the Jobs table when the client has no lists yet
//   26:58  the Upload list button while a file uploads
//   26:60  the only status words: Running (records still queued or running), Done (none pending), Failed (all failed)
//   26:64  upload errors: the upload route's own messages (workspace/app/api/base/route.ts), word for word
export default function C5StatesApproved26Oct() {
  return (
    <div className="bg-[#f4f6fa] content-stretch flex flex-col gap-[16px] items-start p-[32px] relative size-full" data-node-id="26:31" data-name="C5 · states (approved 26 Oct)">
      <div className="[word-break:break-word] bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col items-start leading-[normal] not-italic overflow-clip px-[20px] py-[8px] relative rounded-[12px] shrink-0 text-[#3d4a66] w-[900px]" data-node-id="26:32" data-name="Jobs · empty">
        <div className="content-stretch flex font-['Inter:Semi_Bold'] font-semibold gap-[12px] items-center overflow-clip py-[10px] relative shrink-0 text-[12px] w-full" data-node-id="26:33" data-name="Header row">
          <p className="flex-[1_0_0] min-w-px relative" data-node-id="26:34">Job</p>
          <p className="relative shrink-0 w-[130px]" data-node-id="26:35">Status</p>
          <p className="relative shrink-0 w-[80px]" data-node-id="26:36">Records</p>
          <p className="relative shrink-0 w-[80px]" data-node-id="26:37">Verified</p>
          <p className="relative shrink-0 w-[90px]" data-node-id="26:38">​</p>
        </div>
        <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[13px] whitespace-nowrap" data-node-id="26:57">No lists yet.</p>
      </div>
      <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[8px] shrink-0" data-node-id="26:58" data-name="Button: Upload list · while uploading">
        <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[14px] whitespace-nowrap" data-node-id="26:59">Uploading…</p>
      </div>
      <div className="[word-break:break-word] content-stretch flex flex-col font-['Inter:Regular'] font-normal gap-[4px] items-start leading-[normal] not-italic overflow-clip relative shrink-0 text-[#001840] text-[13px] whitespace-nowrap" data-node-id="26:60" data-name="Status words (one per job)">
        <p className="relative shrink-0" data-node-id="26:61">Running</p>
        <p className="relative shrink-0" data-node-id="26:62">Done</p>
        <p className="relative shrink-0" data-node-id="26:63">Failed</p>
      </div>
      <div className="[word-break:break-word] content-stretch flex flex-col font-['Inter:Regular'] font-normal gap-[4px] items-start leading-[normal] not-italic overflow-clip relative shrink-0 text-[#e80008] text-[13px] whitespace-nowrap" data-node-id="26:64" data-name="Upload errors (the route's own messages, word for word)">
        <p className="relative shrink-0" data-node-id="26:65">file over 80 MB; split it</p>
        <p className="relative shrink-0" data-node-id="26:66">no rows found; first line must be a header</p>
        <p className="relative shrink-0" data-node-id="26:67">max 100,000 rows per upload; split the file</p>
        <p className="relative shrink-0" data-node-id="26:68">Tank unavailable</p>
      </div>
    </div>
  );
}
