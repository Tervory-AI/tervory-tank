// Figma's own code for frame 12:2, exported 25 Oct 2026 with get_design_context, word for word.
// Re-exported 25 Oct 2026, 16:20 PT, after the founder's approved answers (dollars, logo, team names).
// NOT production code: it's the measurement sheet. Rebuild it in the Workspace's own CSS so the result looks the same.
// The only change from Figma: the temporary Figma image links now point to the files in ./assets/.
// Every text below marked as DATA in SPEC.md is sample data. Fill it from the real source.
const imgStatusDot = "./assets/status-dot-waiting.svg";
const imgStatusDot1 = "./assets/status-dot-ready.svg";
const imgStatusDot2 = "./assets/status-dot-in-progress.svg";

export default function ClientDashboardCleanNorthwindLawZa() {
  return (
    <div className="bg-[#f4f6fa] content-stretch flex items-start relative size-full" data-node-id="12:2" data-name="Client dashboard · clean (Northwind Law, US)">
      <div className="bg-[#001840] content-stretch flex flex-col gap-[6px] h-full items-start overflow-clip pt-[22px] px-[16px] relative shrink-0 w-[220px]" data-node-id="12:3" data-name="Sidebar">
        <div className="content-stretch flex items-start overflow-clip pb-[18px] relative shrink-0" data-node-id="12:4" data-name="Logo · tervory-logo-reversed.png · 180 wide">
          {/* The real logo file, workspace/public/brand/tervory-logo-reversed.png, 180 × 33, fit. */}
          <img alt="Tervory AI" className="block h-[33px] w-[180px] object-contain" data-node-id="19:2" src="/brand/tervory-logo-reversed.png" />
        </div>
        <div className="bg-[#22345a] content-stretch flex items-start overflow-clip px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" data-node-id="12:7" data-name="Nav: Home">
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[15px] text-white whitespace-nowrap" data-node-id="12:8">
            Home
          </p>
        </div>
        <div className="content-stretch flex items-start overflow-clip px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" data-node-id="12:9" data-name="Nav: Chats">
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[15px] text-white whitespace-nowrap" data-node-id="12:10">
            Chats
          </p>
        </div>
        <div className="content-stretch flex items-start overflow-clip px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" data-node-id="12:11" data-name="Nav: Files">
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[15px] text-white whitespace-nowrap" data-node-id="12:12">
            Files
          </p>
        </div>
        <div className="content-stretch flex items-start overflow-clip px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" data-node-id="12:13" data-name="Nav: Billing">
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[15px] text-white whitespace-nowrap" data-node-id="12:14">
            Billing
          </p>
        </div>
        <div className="content-stretch flex items-start overflow-clip px-[12px] py-[10px] relative rounded-[8px] shrink-0 w-full" data-node-id="12:15" data-name="Nav: Settings">
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[15px] text-white whitespace-nowrap" data-node-id="12:16">
            Settings
          </p>
        </div>
      </div>
      <div className="content-stretch flex flex-[1_0_0] flex-col gap-[24px] h-full items-start min-w-px overflow-clip px-[64px] py-[48px] relative" data-node-id="12:17" data-name="Main">
        <div className="content-stretch flex gap-[12px] items-center overflow-clip relative shrink-0 w-full" data-node-id="12:18" data-name="Header">
          <p className="[word-break:break-word] font-['Jost:Light'] font-light leading-[normal] relative shrink-0 text-[#001840] text-[34px] whitespace-nowrap" data-node-id="12:19">
            Good morning, Thandi
          </p>
          <div className="flex-[1_0_0] h-px min-w-px relative" data-node-id="12:20" data-name="spacer" />
          <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[14px] whitespace-nowrap" data-node-id="12:21">
            Northwind Law
          </p>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex gap-[10px] items-center overflow-clip pl-[22px] pr-[12px] py-[16px] relative rounded-[16px] shrink-0 w-full" data-node-id="12:22" data-name="Ask">
          <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#8c94a6] text-[18px]" data-node-id="12:23">
            What do you need today?
          </p>
          <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex items-start overflow-clip px-[14px] py-[8px] relative rounded-[10px] shrink-0" data-node-id="12:24" data-name="Button: Add a file">
            <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[13px] whitespace-nowrap" data-node-id="12:25">
              Add a file
            </p>
          </div>
          <div className="bg-[#001840] content-stretch flex items-start overflow-clip px-[14px] py-[8px] relative rounded-[10px] shrink-0" data-node-id="12:26" data-name="Button: Go">
            <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[13px] text-white whitespace-nowrap" data-node-id="12:27">
              Go
            </p>
          </div>
        </div>
        <div className="[word-break:break-word] content-stretch flex gap-[16px] items-start leading-[normal] overflow-clip relative shrink-0 w-full whitespace-nowrap" data-node-id="12:28" data-name="This month">
          <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[22px] relative rounded-[16px]" data-node-id="12:29" data-name="Jobs done this month">
            <p className="font-['Inter:Regular'] font-normal not-italic relative shrink-0 text-[#3d4a66] text-[14px]" data-node-id="12:30">
              Jobs done this month
            </p>
            <p className="font-['Jost:Light'] font-light relative shrink-0 text-[#001840] text-[40px]" data-node-id="12:31">
              67
            </p>
          </div>
          <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[22px] relative rounded-[16px]" data-node-id="12:32" data-name="You saved">
            <p className="font-['Inter:Regular'] font-normal not-italic relative shrink-0 text-[#3d4a66] text-[14px]" data-node-id="12:33">
              You saved
            </p>
            <p className="font-['Jost:Light'] font-light relative shrink-0 text-[#1e7a46] text-[40px]" data-node-id="12:34">
              $8,557
            </p>
          </div>
          <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[22px] relative rounded-[16px]" data-node-id="12:35" data-name="Credits left">
            <p className="font-['Inter:Regular'] font-normal not-italic relative shrink-0 text-[#3d4a66] text-[14px]" data-node-id="12:36">
              Credits left
            </p>
            <p className="font-['Jost:Light'] font-light relative shrink-0 text-[#001840] text-[40px]" data-node-id="12:37">
              18,420
            </p>
          </div>
        </div>
        <div className="content-stretch flex gap-[16px] items-start overflow-clip relative shrink-0 w-full" data-node-id="12:38" data-name="Two columns">
          <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[10px] items-start min-w-px overflow-clip p-[22px] relative rounded-[16px]" data-node-id="12:39" data-name="Waiting on you">
            <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[17px] whitespace-nowrap" data-node-id="12:40">
              Waiting on you
            </p>
            <div className="content-stretch flex gap-[8px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="12:41" data-name="Item">
              <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="12:42">
                Search the web for 212 businesses? About $20
              </p>
              <div className="bg-[#001840] content-stretch flex items-start overflow-clip px-[14px] py-[8px] relative rounded-[10px] shrink-0" data-node-id="12:43" data-name="Button: Yes">
                <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[13px] text-white whitespace-nowrap" data-node-id="12:44">
                  Yes
                </p>
              </div>
              <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex items-start overflow-clip px-[14px] py-[8px] relative rounded-[10px] shrink-0" data-node-id="12:45" data-name="Button: No">
                <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[13px] whitespace-nowrap" data-node-id="12:46">
                  No
                </p>
              </div>
            </div>
            <div className="content-stretch flex gap-[8px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="12:47" data-name="Item">
              <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="12:48">
                Lease review is ready to read
              </p>
              <div className="bg-[#001840] content-stretch flex items-start overflow-clip px-[14px] py-[8px] relative rounded-[10px] shrink-0" data-node-id="12:49" data-name="Button: Open">
                <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[13px] text-white whitespace-nowrap" data-node-id="12:50">
                  Open
                </p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[10px] items-start min-w-px overflow-clip p-[22px] relative rounded-[16px]" data-node-id="12:51" data-name="Recent work">
            <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[#001840] text-[17px] whitespace-nowrap" data-node-id="12:52">
              Recent work
            </p>
            <div className="content-stretch flex gap-[10px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="12:53" data-name="Job">
              <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="12:54">
                Delaware dealer list
              </p>
              <div className="relative shrink-0 size-[10px]" data-node-id="12:55" data-name="Status dot">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} />
              </div>
              <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[14px] whitespace-nowrap" data-node-id="12:56">
                Waiting on you
              </p>
            </div>
            <div className="content-stretch flex gap-[10px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="12:57" data-name="Job">
              <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="12:58">
                Lease review
              </p>
              <div className="relative shrink-0 size-[10px]" data-node-id="12:59" data-name="Status dot">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot1} />
              </div>
              <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[14px] whitespace-nowrap" data-node-id="12:60">
                Ready
              </p>
            </div>
            <div className="content-stretch flex gap-[10px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="12:61" data-name="Job">
              <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="12:62">
                Competitor prices
              </p>
              <div className="relative shrink-0 size-[10px]" data-node-id="12:63" data-name="Status dot">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot1} />
              </div>
              <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[14px] whitespace-nowrap" data-node-id="12:64">
                Ready
              </p>
            </div>
            <div className="content-stretch flex gap-[10px] items-center overflow-clip py-[6px] relative shrink-0 w-full" data-node-id="12:65" data-name="Job">
              <p className="[word-break:break-word] flex-[1_0_0] font-['Inter:Regular'] font-normal leading-[normal] min-w-px not-italic relative text-[#001840] text-[15px]" data-node-id="12:66">
                Q3 dealer list
              </p>
              <div className="relative shrink-0 size-[10px]" data-node-id="12:67" data-name="Status dot">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot2} />
              </div>
              <p className="[word-break:break-word] font-['Inter:Regular'] font-normal leading-[normal] not-italic relative shrink-0 text-[#3d4a66] text-[14px] whitespace-nowrap" data-node-id="12:68">
                In progress
              </p>
            </div>
          </div>
        </div>
        <div className="[word-break:break-word] bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-col gap-[10px] items-start leading-[normal] not-italic overflow-clip p-[22px] relative rounded-[16px] shrink-0 w-full whitespace-nowrap" data-node-id="12:69" data-name="Your team">
          <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[17px]" data-node-id="12:70">
            Your team
          </p>
          <div className="content-stretch flex gap-[12px] items-start overflow-clip relative shrink-0 w-full" data-node-id="12:71" data-name="Members">
            <div className="bg-[#f4f6fa] content-stretch flex flex-[1_0_0] flex-col gap-[2px] items-start min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[12px]" data-node-id="12:72" data-name="Member: Base">
              <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[15px]" data-node-id="12:73">
                Base
              </p>
              <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[#3d4a66] text-[13px]" data-node-id="12:74">
                Business lists
              </p>
            </div>
            <div className="bg-[#f4f6fa] content-stretch flex flex-[1_0_0] flex-col gap-[2px] items-start min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[12px]" data-node-id="12:75" data-name="Member: Tiger">
              <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[15px]" data-node-id="12:76">
                Tiger
              </p>
              <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[#3d4a66] text-[13px]" data-node-id="12:77">
                Prices
              </p>
            </div>
            <div className="bg-[#f4f6fa] content-stretch flex flex-[1_0_0] flex-col gap-[2px] items-start min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[12px]" data-node-id="12:78" data-name="Member: Market Lab">
              <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[15px]" data-node-id="12:79">
                Market Lab
              </p>
              <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[#3d4a66] text-[13px]" data-node-id="12:80">
                Market research
              </p>
            </div>
            <div className="bg-[#f4f6fa] content-stretch flex flex-[1_0_0] flex-col gap-[2px] items-start min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[12px]" data-node-id="12:81" data-name="Member: Zenas">
              <p className="font-['Inter:Semi_Bold'] font-semibold relative shrink-0 text-[#001840] text-[15px]" data-node-id="12:82">
                Zenas
              </p>
              <p className="font-['Inter:Regular'] font-normal relative shrink-0 text-[#3d4a66] text-[13px]" data-node-id="12:83">
                Legal
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
