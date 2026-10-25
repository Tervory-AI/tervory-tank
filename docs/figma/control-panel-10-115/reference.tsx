// Figma's own code for frame 10:115, exported 25 Oct 2026 with get_design_context.
// Re-exported 25 Oct 2026, 16:20 PT, after the founder's approved answers (Autumbra, logo; South Africa server row,
// Apollo figures and line, and the sample-figures footer removed).
// NOT production code: it's the measurement sheet. Rebuild it in the Workspace's own CSS so the result looks the same.
// Changes from Figma's output, and nothing else:
//  - the temporary Figma image links now point to the files in ./assets/;
//  - to keep it readable, repeated no-effect classes (leading-[normal], not-italic, overflow-clip, relative,
//    shrink-0, [word-break:break-word], content-stretch) are dropped from inner elements;
//  - a few comments (/* ... */) sum up repeated rows.
// Every text, font, size, colour, gap, padding, radius and width is exactly as Figma gave it. frame.png is the check.
// Every text below marked as DATA in SPEC.md is sample data. Fill it from the real source.
const imgStatusDot = "./assets/status-dot-green.svg";
const imgSparkline = "./assets/sparkline-signups.svg";
const imgSparkline1 = "./assets/sparkline-paying-clients.svg";
const imgSparkline2 = "./assets/sparkline-work-done.svg";
const imgSparkline3 = "./assets/sparkline-spent.svg";
const imgSparkline4 = "./assets/sparkline-saved.svg";
const imgLineChart = "./assets/line-chart-cost-per-record.svg";
const imgStatusDot1 = "./assets/status-dot-amber.svg";
const imgStatusDot2 = "./assets/status-dot-grey.svg";
const imgSwitch = "./assets/switch-on.svg";
const imgSwitch1 = "./assets/switch-off.svg";

export default function FounderControlPanelEverythingOnOneScreen() {
  return (
    <div className="bg-[#f4f6fa] content-stretch flex flex-col gap-[18px] items-start pb-[32px] pt-[24px] px-[32px] relative size-full" data-node-id="10:115" data-name="Founder control panel · everything on one screen">
      <div className="content-stretch flex gap-[14px] items-center overflow-clip relative shrink-0 w-full" data-node-id="10:116" data-name="Top bar">
        <div className="flex items-start relative shrink-0" data-node-id="10:117" data-name="Logo · tervory-logo.png · 180 wide">
          {/* The real logo file, workspace/public/brand/tervory-logo.png, 180 × 33, fit. */}
          <img alt="Tervory AI" className="block h-[33px] w-[180px] object-contain" data-node-id="19:3" src="/brand/tervory-logo.png" />
        </div>
        <p className="[word-break:break-word] font-['Jost:Light'] font-light leading-[normal] relative shrink-0 text-[#3d4a66] text-[22px] whitespace-nowrap" data-node-id="10:120">Control panel</p>
        <div className="flex-[1_0_0] h-px min-w-px relative" data-node-id="10:121" data-name="spacer" />
        <div className="bg-[#eaf6ef] content-stretch flex gap-[8px] items-center overflow-clip px-[14px] py-[8px] relative rounded-[999px] shrink-0" data-node-id="10:122" data-name="Health">
          <div className="relative shrink-0 size-[10px]" data-node-id="10:123" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
          <p className="[word-break:break-word] font-['Inter:Medium'] font-medium leading-[normal] not-italic relative shrink-0 text-[#1e7a46] text-[13px] whitespace-nowrap" data-node-id="10:124">All systems normal · Autumbra on watch</p>
        </div>
        <div className="bg-[#e80008] content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[8px] shrink-0" data-node-id="10:125" data-name="Button: Pause all paid work">
          <p className="[word-break:break-word] font-['Inter:Semi_Bold'] font-semibold leading-[normal] not-italic relative shrink-0 text-[14px] text-white whitespace-nowrap" data-node-id="10:126">Pause all paid work</p>
        </div>
      </div>

      {/* Key numbers: five KPI cards. Each card: label 13px #3d4a66, number JetBrains Mono 26px, sub-row 12px #3d4a66 + 120x32 sparkline. */}
      <div className="content-stretch flex gap-[14px] items-start overflow-clip relative shrink-0 w-full" data-node-id="10:127" data-name="Key numbers">
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[20px] relative rounded-[14px]" data-node-id="10:128" data-name="KPI: Sign-ups">
          <p className="font-['Inter:Regular'] text-[#3d4a66] text-[13px] whitespace-nowrap" data-node-id="10:129">Sign-ups</p>
          <p className="font-['JetBrains_Mono:Regular'] text-[#001840] text-[26px] whitespace-nowrap" data-node-id="10:130">214</p>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:131" data-name="sub">
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:132">+31 this week</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:133" data-name="spacer" />
            <div className="h-[32px] relative shrink-0 w-[120px]" data-node-id="10:134" data-name="Sparkline"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSparkline} /></div>
          </div>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[20px] relative rounded-[14px]" data-node-id="10:136" data-name="KPI: Paying clients">
          <p className="font-['Inter:Regular'] text-[#3d4a66] text-[13px] whitespace-nowrap" data-node-id="10:137">Paying clients</p>
          <p className="font-['JetBrains_Mono:Regular'] text-[#001840] text-[26px] whitespace-nowrap" data-node-id="10:138">9</p>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:139" data-name="sub">
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:140">+2 this week</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:141" data-name="spacer" />
            <div className="h-[32px] relative shrink-0 w-[120px]" data-node-id="10:142" data-name="Sparkline"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSparkline1} /></div>
          </div>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[20px] relative rounded-[14px]" data-node-id="10:144" data-name="KPI: Work done today">
          <p className="font-['Inter:Regular'] text-[#3d4a66] text-[13px] whitespace-nowrap" data-node-id="10:145">Work done today</p>
          <p className="font-['JetBrains_Mono:Regular'] text-[#001840] text-[26px] whitespace-nowrap" data-node-id="10:146">4,812</p>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:147" data-name="sub">
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:148">71% by code, no model</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:149" data-name="spacer" />
            <div className="h-[32px] relative shrink-0 w-[120px]" data-node-id="10:150" data-name="Sparkline"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSparkline2} /></div>
          </div>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[20px] relative rounded-[14px]" data-node-id="10:152" data-name="KPI: Spent this month">
          <p className="font-['Inter:Regular'] text-[#3d4a66] text-[13px] whitespace-nowrap" data-node-id="10:153">Spent this month</p>
          <p className="font-['JetBrains_Mono:Regular'] text-[#001840] text-[26px] whitespace-nowrap" data-node-id="10:154">$212.40</p>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:155" data-name="sub">
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:156">budget $600</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:157" data-name="spacer" />
            <div className="h-[32px] relative shrink-0 w-[120px]" data-node-id="10:158" data-name="Sparkline"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSparkline3} /></div>
          </div>
        </div>
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[6px] items-start min-w-px overflow-clip p-[20px] relative rounded-[14px]" data-node-id="10:160" data-name="KPI: Saved this month">
          <p className="font-['Inter:Regular'] text-[#3d4a66] text-[13px] whitespace-nowrap" data-node-id="10:161">Saved this month</p>
          <p className="font-['JetBrains_Mono:Regular'] text-[#1e7a46] text-[26px] whitespace-nowrap" data-node-id="10:162">$3,691.70</p>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:163" data-name="sub">
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:164">vs top models</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:165" data-name="spacer" />
            <div className="h-[32px] relative shrink-0 w-[120px]" data-node-id="10:166" data-name="Sparkline"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSparkline4} /></div>
          </div>
        </div>
      </div>

      <div className="content-stretch flex gap-[14px] items-start overflow-clip relative shrink-0 w-full" data-node-id="10:168" data-name="Case study and needs you">
        <div className="bg-white border border-[#b8bfd0] border-solid content-stretch flex flex-[1_0_0] flex-col gap-[12px] items-start min-w-px overflow-clip p-[20px] relative rounded-[14px]" data-node-id="10:169" data-name="Case study: AmmoSync on Base">
          <div className="flex gap-[8px] items-start w-full" data-node-id="10:170" data-name="Head">
            <p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[16px] whitespace-nowrap" data-node-id="10:171">Case study · AmmoSync on Base</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:172" data-name="spacer" />
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:173">ATF list · 74,012 licences</p>
          </div>
          <div className="flex gap-[20px] items-start w-full" data-node-id="10:174" data-name="Charts">
            <div className="flex flex-[1_0_0] flex-col gap-[8px] items-start min-w-px" data-node-id="10:175" data-name="Chart: verified records by state">
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:176">Verified records by state</p>
              {/* Bars: 170 high, 14px gap between states. Each state = pair (3px gap) of 14px-wide bars, radius 3:
                  Licences #d6deeb, Verified #001840; label 11px #3d4a66 under it, 4px gap.
                  Frame heights (Licences/Verified): DE 120/98, VT 104/88, RI 96/80, WY 140/120, TX 165/150, FL 160/130, CA 150/60. */}
              <div className="flex gap-[14px] h-[170px] items-end" data-node-id="10:177" data-name="Bars">
                <div className="flex flex-col gap-[4px] items-center" data-node-id="10:178" data-name="DE">
                  <div className="flex gap-[3px] items-end" data-node-id="10:179" data-name="pair">
                    <div className="bg-[#d6deeb] h-[120px] rounded-[3px] w-[14px]" data-node-id="10:180" data-name="Licences" />
                    <div className="bg-[#001840] h-[98px] rounded-[3px] w-[14px]" data-node-id="10:181" data-name="Verified" />
                  </div>
                  <p className="font-['Inter:Regular'] text-[#3d4a66] text-[11px]" data-node-id="10:182">DE</p>
                </div>
                <div className="flex flex-col gap-[4px] items-center" data-node-id="10:183" data-name="VT">
                  <div className="flex gap-[3px] items-end" data-node-id="10:184" data-name="pair">
                    <div className="bg-[#d6deeb] h-[104px] rounded-[3px] w-[14px]" data-node-id="10:185" data-name="Licences" />
                    <div className="bg-[#001840] h-[88px] rounded-[3px] w-[14px]" data-node-id="10:186" data-name="Verified" />
                  </div>
                  <p className="font-['Inter:Regular'] text-[#3d4a66] text-[11px]" data-node-id="10:187">VT</p>
                </div>
                <div className="flex flex-col gap-[4px] items-center" data-node-id="10:188" data-name="RI">
                  <div className="flex gap-[3px] items-end" data-node-id="10:189" data-name="pair">
                    <div className="bg-[#d6deeb] h-[96px] rounded-[3px] w-[14px]" data-node-id="10:190" data-name="Licences" />
                    <div className="bg-[#001840] h-[80px] rounded-[3px] w-[14px]" data-node-id="10:191" data-name="Verified" />
                  </div>
                  <p className="font-['Inter:Regular'] text-[#3d4a66] text-[11px]" data-node-id="10:192">RI</p>
                </div>
                <div className="flex flex-col gap-[4px] items-center" data-node-id="10:193" data-name="WY">
                  <div className="flex gap-[3px] items-end" data-node-id="10:194" data-name="pair">
                    <div className="bg-[#d6deeb] h-[140px] rounded-[3px] w-[14px]" data-node-id="10:195" data-name="Licences" />
                    <div className="bg-[#001840] h-[120px] rounded-[3px] w-[14px]" data-node-id="10:196" data-name="Verified" />
                  </div>
                  <p className="font-['Inter:Regular'] text-[#3d4a66] text-[11px]" data-node-id="10:197">WY</p>
                </div>
                <div className="flex flex-col gap-[4px] items-center" data-node-id="10:198" data-name="TX">
                  <div className="flex gap-[3px] items-end" data-node-id="10:199" data-name="pair">
                    <div className="bg-[#d6deeb] h-[165px] rounded-[3px] w-[14px]" data-node-id="10:200" data-name="Licences" />
                    <div className="bg-[#001840] h-[150px] rounded-[3px] w-[14px]" data-node-id="10:201" data-name="Verified" />
                  </div>
                  <p className="font-['Inter:Regular'] text-[#3d4a66] text-[11px]" data-node-id="10:202">TX</p>
                </div>
                <div className="flex flex-col gap-[4px] items-center" data-node-id="10:203" data-name="FL">
                  <div className="flex gap-[3px] items-end" data-node-id="10:204" data-name="pair">
                    <div className="bg-[#d6deeb] h-[160px] rounded-[3px] w-[14px]" data-node-id="10:205" data-name="Licences" />
                    <div className="bg-[#001840] h-[130px] rounded-[3px] w-[14px]" data-node-id="10:206" data-name="Verified" />
                  </div>
                  <p className="font-['Inter:Regular'] text-[#3d4a66] text-[11px]" data-node-id="10:207">FL</p>
                </div>
                <div className="flex flex-col gap-[4px] items-center" data-node-id="10:208" data-name="CA">
                  <div className="flex gap-[3px] items-end" data-node-id="10:209" data-name="pair">
                    <div className="bg-[#d6deeb] h-[150px] rounded-[3px] w-[14px]" data-node-id="10:210" data-name="Licences" />
                    <div className="bg-[#001840] h-[60px] rounded-[3px] w-[14px]" data-node-id="10:211" data-name="Verified" />
                  </div>
                  <p className="font-['Inter:Regular'] text-[#3d4a66] text-[11px]" data-node-id="10:212">CA</p>
                </div>
              </div>
              <div className="flex font-['Inter:Regular'] gap-[12px] items-start text-[11px] whitespace-nowrap" data-node-id="10:213" data-name="Legend">
                <p className="text-[#001840]" data-node-id="10:214">■ Verified</p>
                <p className="text-[#8c94a6]" data-node-id="10:215">■ Licences</p>
              </div>
            </div>
            <div className="flex flex-[1_0_0] flex-col gap-[8px] items-start min-w-px" data-node-id="10:216" data-name="Chart: cost per verified record">
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:217">Cost per verified record</p>
              <div className="h-[170px] relative shrink-0 w-[360px]" data-node-id="10:218" data-name="Line chart"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgLineChart} /></div>
              <div className="flex font-['Inter:Regular'] gap-[12px] items-start text-[11px] whitespace-nowrap" data-node-id="10:222" data-name="Legend">
                <p className="text-[#001840]" data-node-id="10:223">— Tervory, falling</p>
              </div>
            </div>
          </div>
          <div className="flex gap-[24px] items-start w-full whitespace-nowrap" data-node-id="10:225" data-name="Headline numbers">
            <div className="flex flex-col gap-[2px] items-start" data-node-id="10:226" data-name="Tervory found">
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:227">Tervory found</p>
              <p className="font-['JetBrains_Mono:Regular'] text-[#001840] text-[18px]" data-node-id="10:228">14,000 records</p>
            </div>
            <div className="flex flex-col gap-[2px] items-start" data-node-id="10:232" data-name="Cost per record">
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:233">Cost per record</p>
              <p className="font-['JetBrains_Mono:Regular'] text-[#1e7a46] text-[18px]" data-node-id="10:234">$0.0004</p>
            </div>
            <div className="flex flex-col gap-[2px] items-start" data-node-id="10:235" data-name="States done">
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:236">States done</p>
              <p className="font-['JetBrains_Mono:Regular'] text-[#001840] text-[18px]" data-node-id="10:237">12 of 50</p>
            </div>
          </div>
          <div className="flex gap-[8px] items-start" data-node-id="10:238" data-name="Actions">
            <div className="bg-[#001840] px-[12px] py-[7px] rounded-[8px]" data-node-id="10:239" data-name="Button: Run next state"><p className="font-['Inter:Semi_Bold'] font-semibold text-[13px] text-white whitespace-nowrap" data-node-id="10:240">Run next state</p></div>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:241" data-name="Button: Export case study"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:242">Export case study</p></div>
          </div>
        </div>

        {/* Needs you: fixed width 520. Items: text 13px #001840 flex-1, row py 6, gap 8. Buttons: primary #001840, green #1e7a46, red #e80008, or white with border #b8bfd0; px 12 py 7, radius 8, 13px semibold. */}
        <div className="bg-white border border-[#b8bfd0] border-solid flex flex-col gap-[12px] items-start p-[20px] rounded-[14px] shrink-0 w-[520px]" data-node-id="10:243" data-name="Needs you">
          <div className="flex items-start w-full" data-node-id="10:244" data-name="Head">
            <p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[16px] whitespace-nowrap" data-node-id="10:245">Needs you</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:246" data-name="spacer" />
            <p className="font-['JetBrains_Mono:Regular'] text-[#e80008] text-[14px] whitespace-nowrap" data-node-id="10:247">5</p>
          </div>
          <div className="flex gap-[8px] items-center py-[6px] w-full" data-node-id="10:248" data-name="Item">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:249">14 skills passed their tests</p>
            <div className="bg-[#001840] px-[12px] py-[7px] rounded-[8px]" data-node-id="10:250" data-name="Button: Approve all"><p className="font-['Inter:Semi_Bold'] font-semibold text-[13px] text-white whitespace-nowrap" data-node-id="10:251">Approve all</p></div>
          </div>
          <div className="flex gap-[8px] items-center py-[6px] w-full" data-node-id="10:252" data-name="Item">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:253">Web search for 212 records · $1.06</p>
            <div className="bg-[#001840] px-[12px] py-[7px] rounded-[8px]" data-node-id="10:254" data-name="Button: Run"><p className="font-['Inter:Semi_Bold'] font-semibold text-[13px] text-white whitespace-nowrap" data-node-id="10:255">Run</p></div>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:256" data-name="Button: Skip"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:257">Skip</p></div>
          </div>
          <div className="flex gap-[8px] items-center py-[6px] w-full" data-node-id="10:258" data-name="Item">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:259">Cheaper model proven for market research · saves $410/mo</p>
            <div className="bg-[#1e7a46] px-[12px] py-[7px] rounded-[8px]" data-node-id="10:260" data-name="Button: Switch"><p className="font-['Inter:Semi_Bold'] font-semibold text-[13px] text-white whitespace-nowrap" data-node-id="10:261">Switch</p></div>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:262" data-name="Button: Later"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:263">Later</p></div>
          </div>
          <div className="flex gap-[8px] items-center py-[6px] w-full" data-node-id="10:264" data-name="Item">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:265">Daily check: 26 examples</p>
            <div className="bg-[#001840] px-[12px] py-[7px] rounded-[8px]" data-node-id="10:266" data-name="Button: Start"><p className="font-['Inter:Semi_Bold'] font-semibold text-[13px] text-white whitespace-nowrap" data-node-id="10:267">Start</p></div>
          </div>
          <div className="flex gap-[8px] items-center py-[6px] w-full" data-node-id="10:268" data-name="Item">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:269">Autumbra: login errors up on app.tervory.com</p>
            <div className="bg-[#e80008] px-[12px] py-[7px] rounded-[8px]" data-node-id="10:270" data-name="Button: Look"><p className="font-['Inter:Semi_Bold'] font-semibold text-[13px] text-white whitespace-nowrap" data-node-id="10:271">Look</p></div>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:272" data-name="Button: Let it fix"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:273">Let it fix</p></div>
          </div>
        </div>
      </div>

      <div className="flex gap-[14px] items-start w-full" data-node-id="10:274" data-name="Squad, sign-ups and controls">
        {/* Squad: rows py 5, gap 10. Dot 10px, name Inter Medium 14px width 96, job 13px #3d4a66 flex-1, button white/border px 12 py 7 radius 8. */}
        <div className="bg-white border border-[#b8bfd0] border-solid flex flex-[1_0_0] flex-col gap-[12px] items-start min-w-px p-[20px] rounded-[14px]" data-node-id="10:275" data-name="Squad">
          <div className="flex items-start w-full" data-node-id="10:276" data-name="Head">
            <p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[16px] whitespace-nowrap" data-node-id="10:277">Squad</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:278" data-name="spacer" />
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[13px] whitespace-nowrap" data-node-id="10:279">Boston ▾</p>
          </div>
          {/* Rows, in this order: [dot, name, job, button]
              10:280 green  Base        "Texas list · 61%"        Pause
              10:286 green  Tiger       "Custom Nation prices"    Pause
              10:292 amber  Market Lab  "Overnight batch"         Pause
              10:298 grey   Rig         "—"                       Start
              10:304 green  Tisan       "Billing page build"      Pause
              10:310 green  Radix       "Scanning PR #214"        Pause
              10:316 green  Zenas       "SA archive · 1,214 done" Pause
              10:322 green  Autumbra    "No open issues"          Pause */}
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:280" data-name="Agent: Base">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:281" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:282">Base</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:283">Texas list · 61%</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:284" data-name="Button: Pause"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:285">Pause</p></div>
          </div>
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:286" data-name="Agent: Tiger">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:287" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:288">Tiger</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:289">Custom Nation prices</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:290" data-name="Button: Pause"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:291">Pause</p></div>
          </div>
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:292" data-name="Agent: Market Lab">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:293" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot1} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:294">Market Lab</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:295">Overnight batch</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:296" data-name="Button: Pause"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:297">Pause</p></div>
          </div>
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:298" data-name="Agent: Rig">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:299" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot2} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:300">Rig</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:301">—</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:302" data-name="Button: Start"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:303">Start</p></div>
          </div>
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:304" data-name="Agent: Tisan">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:305" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:306">Tisan</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:307">Billing page build</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:308" data-name="Button: Pause"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:309">Pause</p></div>
          </div>
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:310" data-name="Agent: Radix">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:311" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:312">Radix</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:313">Scanning PR #214</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:314" data-name="Button: Pause"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:315">Pause</p></div>
          </div>
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:316" data-name="Agent: Zenas">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:317" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:318">Zenas</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:319">SA archive · 1,214 done</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:320" data-name="Button: Pause"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:321">Pause</p></div>
          </div>
          <div className="flex gap-[10px] items-center py-[5px] w-full" data-node-id="10:322" data-name="Agent: Autumbra">
            <div className="relative shrink-0 size-[10px]" data-node-id="10:323" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
            <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[14px] w-[96px]" data-node-id="10:324">Autumbra</p>
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#3d4a66] text-[13px]" data-node-id="10:325">No open issues</p>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:326" data-name="Button: Pause"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:327">Pause</p></div>
          </div>
        </div>

        {/* Latest sign-ups: rows py 5, gap 8. Name Inter Medium 13px #001840; "Company · Country" 12px #3d4a66 (1px gap);
            plan pill bg #f4f6fa radius 999 px 8 py 3, Inter Medium 11px; time 12px #3d4a66. */}
        <div className="bg-white border border-[#b8bfd0] border-solid flex flex-[1_0_0] flex-col gap-[12px] items-start min-w-px p-[20px] rounded-[14px]" data-node-id="10:328" data-name="Sign-ups">
          <div className="flex items-start w-full" data-node-id="10:329" data-name="Head">
            <p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[16px] whitespace-nowrap" data-node-id="10:330">Latest sign-ups</p>
            <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:331" data-name="spacer" />
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:332" data-name="Button: All 214"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:333">All 214</p></div>
          </div>
          {/* 10:334 Thandi Mokoena / Northwind Law · South Africa / Team / 2h ago
              10:341 James Ortega / Lone Star Arms · United States / Trial / 5h ago
              10:348 Priya Naidoo / Coastal Imports · South Africa / Starter / Yesterday
              10:355 Mark Ellis / Ellis Outdoor · United States / Trial / Yesterday
              10:362 Lerato Dube / Dube Attorneys · South Africa / Trial / 2 days ago */}
          <div className="flex gap-[8px] items-start py-[5px] w-full" data-node-id="10:334" data-name="Sign-up">
            <div className="flex flex-[1_0_0] flex-col gap-px items-start min-w-px whitespace-nowrap" data-node-id="10:335" data-name="Who">
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[13px]" data-node-id="10:336">Thandi Mokoena</p>
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:337">Northwind Law · South Africa</p>
            </div>
            <div className="bg-[#f4f6fa] px-[8px] py-[3px] rounded-[999px]" data-node-id="10:338" data-name="Plan"><p className="font-['Inter:Medium'] font-medium text-[#001840] text-[11px] whitespace-nowrap" data-node-id="10:339">Team</p></div>
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:340">2h ago</p>
          </div>
          <div className="flex gap-[8px] items-start py-[5px] w-full" data-node-id="10:341" data-name="Sign-up">
            <div className="flex flex-[1_0_0] flex-col gap-px items-start min-w-px whitespace-nowrap" data-node-id="10:342" data-name="Who">
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[13px]" data-node-id="10:343">James Ortega</p>
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:344">Lone Star Arms · United States</p>
            </div>
            <div className="bg-[#f4f6fa] px-[8px] py-[3px] rounded-[999px]" data-node-id="10:345" data-name="Plan"><p className="font-['Inter:Medium'] font-medium text-[#001840] text-[11px] whitespace-nowrap" data-node-id="10:346">Trial</p></div>
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:347">5h ago</p>
          </div>
          <div className="flex gap-[8px] items-start py-[5px] w-full" data-node-id="10:348" data-name="Sign-up">
            <div className="flex flex-[1_0_0] flex-col gap-px items-start min-w-px whitespace-nowrap" data-node-id="10:349" data-name="Who">
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[13px]" data-node-id="10:350">Priya Naidoo</p>
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:351">Coastal Imports · South Africa</p>
            </div>
            <div className="bg-[#f4f6fa] px-[8px] py-[3px] rounded-[999px]" data-node-id="10:352" data-name="Plan"><p className="font-['Inter:Medium'] font-medium text-[#001840] text-[11px] whitespace-nowrap" data-node-id="10:353">Starter</p></div>
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:354">Yesterday</p>
          </div>
          <div className="flex gap-[8px] items-start py-[5px] w-full" data-node-id="10:355" data-name="Sign-up">
            <div className="flex flex-[1_0_0] flex-col gap-px items-start min-w-px whitespace-nowrap" data-node-id="10:356" data-name="Who">
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[13px]" data-node-id="10:357">Mark Ellis</p>
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:358">Ellis Outdoor · United States</p>
            </div>
            <div className="bg-[#f4f6fa] px-[8px] py-[3px] rounded-[999px]" data-node-id="10:359" data-name="Plan"><p className="font-['Inter:Medium'] font-medium text-[#001840] text-[11px] whitespace-nowrap" data-node-id="10:360">Trial</p></div>
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:361">Yesterday</p>
          </div>
          <div className="flex gap-[8px] items-start py-[5px] w-full" data-node-id="10:362" data-name="Sign-up">
            <div className="flex flex-[1_0_0] flex-col gap-px items-start min-w-px whitespace-nowrap" data-node-id="10:363" data-name="Who">
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[13px]" data-node-id="10:364">Lerato Dube</p>
              <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px]" data-node-id="10:365">Dube Attorneys · South Africa</p>
            </div>
            <div className="bg-[#f4f6fa] px-[8px] py-[3px] rounded-[999px]" data-node-id="10:366" data-name="Plan"><p className="font-['Inter:Medium'] font-medium text-[#001840] text-[11px] whitespace-nowrap" data-node-id="10:367">Trial</p></div>
            <p className="font-['Inter:Regular'] text-[#3d4a66] text-[12px] whitespace-nowrap" data-node-id="10:368">2 days ago</p>
          </div>
        </div>

        {/* Controls: fixed width 360. Toggles: label 13px #001840 flex-1, switch 40x22. */}
        <div className="bg-white border border-[#b8bfd0] border-solid flex flex-col gap-[12px] items-start p-[20px] rounded-[14px] shrink-0 w-[360px]" data-node-id="10:369" data-name="Controls">
          <p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[16px] whitespace-nowrap" data-node-id="10:370">Controls</p>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:371" data-name="Toggle: Shadow checks on every model call">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:372">Shadow checks on every model call</p>
            <div className="h-[22px] relative shrink-0 w-[40px]" data-node-id="10:373" data-name="Switch"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSwitch} /></div>
          </div>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:375" data-name="Toggle: Overnight half-price batches">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:376">Overnight half-price batches</p>
            <div className="h-[22px] relative shrink-0 w-[40px]" data-node-id="10:377" data-name="Switch"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSwitch} /></div>
          </div>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:379" data-name="Toggle: Paid tools without asking">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:380">Paid tools without asking</p>
            <div className="h-[22px] relative shrink-0 w-[40px]" data-node-id="10:381" data-name="Switch"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSwitch1} /></div>
          </div>
          <div className="flex gap-[8px] items-center w-full" data-node-id="10:383" data-name="Toggle: Squad builds Tervory">
            <p className="flex-[1_0_0] font-['Inter:Regular'] min-w-px text-[#001840] text-[13px]" data-node-id="10:384">Squad builds Tervory</p>
            <div className="h-[22px] relative shrink-0 w-[40px]" data-node-id="10:385" data-name="Switch"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSwitch} /></div>
          </div>
          <div className="flex flex-col gap-[6px] items-start w-full" data-node-id="10:387" data-name="Daily budget">
            <div className="flex items-start w-full" data-node-id="10:388" data-name="Head">
              <p className="font-['Inter:Regular'] text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:389">Daily budget</p>
              <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:390" data-name="spacer" />
              <p className="font-['JetBrains_Mono:Regular'] text-[#001840] text-[12px] whitespace-nowrap" data-node-id="10:391">$20 · $7.10 used</p>
            </div>
            <div className="bg-[#d6deeb] flex h-[8px] items-start overflow-clip rounded-[999px] w-full" data-node-id="10:392" data-name="Bar">
              <div className="bg-[#001840] h-[8px] rounded-[999px] w-[107px]" data-node-id="10:393" data-name="Rectangle" />
            </div>
          </div>
          <div className="flex flex-col gap-[4px] items-start w-full" data-node-id="10:394" data-name="Servers">
            <p className="font-['Inter:Regular'] text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:395">Servers</p>
            <div className="flex gap-[8px] items-start w-full" data-node-id="10:396" data-name="Boston">
              <div className="relative shrink-0 size-[10px]" data-node-id="10:397" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[12px] whitespace-nowrap" data-node-id="10:398">Boston</p>
              <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:399" data-name="spacer" />
              <p className="font-['JetBrains_Mono:Regular'] text-[#3d4a66] text-[11px] whitespace-nowrap" data-node-id="10:400">CPU 34% · memory 61%</p>
            </div>
            <div className="flex gap-[8px] items-start w-full" data-node-id="10:406" data-name="Storage">
              <div className="relative shrink-0 size-[10px]" data-node-id="10:407" data-name="Status dot"><img alt="" className="absolute block inset-0 max-w-none size-full" src={imgStatusDot} /></div>
              <p className="font-['Inter:Medium'] font-medium text-[#001840] text-[12px] whitespace-nowrap" data-node-id="10:408">Storage</p>
              <div className="flex-[1_0_0] h-px min-w-px" data-node-id="10:409" data-name="spacer" />
              <p className="font-['JetBrains_Mono:Regular'] text-[#3d4a66] text-[11px] whitespace-nowrap" data-node-id="10:410">R2 · 41 GB of 1 TB</p>
            </div>
          </div>
          <div className="flex gap-[8px] items-start w-full" data-node-id="10:411" data-name="Quick actions">
            <div className="bg-[#001840] px-[12px] py-[7px] rounded-[8px]" data-node-id="10:412" data-name="Button: Open the window"><p className="font-['Inter:Semi_Bold'] font-semibold text-[13px] text-white whitespace-nowrap" data-node-id="10:413">Open the window</p></div>
            <div className="bg-white border border-[#b8bfd0] border-solid px-[12px] py-[7px] rounded-[8px]" data-node-id="10:414" data-name="Button: Proof report"><p className="font-['Inter:Semi_Bold'] font-semibold text-[#001840] text-[13px] whitespace-nowrap" data-node-id="10:415">Proof report</p></div>
          </div>
        </div>
      </div>
    </div>
  );
}
