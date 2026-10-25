/**
 * Fixture-only demo content for the squad product hosts.
 * No Tank, vault or API keys are needed; nothing here is live client data.
 */

export const DEMO_BANNER = "Example / demo — not live client data.";

export type DemoItem = {
  id: string;
  title: string;
  meta: string;
  status: string;
  detail: string[];
};

export type DemoSection = {
  id: string;
  label: string;
  items: DemoItem[];
};

export type DemoProduct = {
  slug: string;
  name: string;
  tagline: string;
  sections: DemoSection[];
};

const item = (id: string, title: string, meta: string, status: string, detail: string[]): DemoItem => ({
  id,
  title,
  meta,
  status,
  detail,
});

export const DEMO_PRODUCTS: readonly DemoProduct[] = [
  {
    slug: "zenas",
    name: "Zenas",
    tagline: "US and South African legal research.",
    sections: [
      {
        id: "matters",
        label: "Matters",
        items: [
          item("m1", "Harlow v. Dunmore Freight", "Contract dispute · US", "Open", [
            "Question: is the late-delivery clause enforceable?",
            "3 sources found. 1 needs a lawyer's check.",
          ]),
          item("m2", "Nkosi Estate — lease review", "Property · South Africa", "Drafting", [
            "Question: does the 2019 lease survive the sale?",
            "2 sources found. Draft memo is half written.",
          ]),
          item("m3", "Brightwater Clinics — vendor terms", "Commercial · US", "Review", [
            "Question: who carries data-breach cost under section 9?",
            "4 sources found. Memo ready for sign-off.",
          ]),
        ],
      },
      {
        id: "deadlines",
        label: "Deadlines",
        items: [
          item("d1", "Reply brief due", "Harlow v. Dunmore · in 6 days", "Soon", ["Court rule counted from service date. Check with the clerk."]),
          item("d2", "Notice period ends", "Nkosi Estate · in 21 days", "Later", ["Thirty days from written notice."]),
        ],
      },
    ],
  },
  {
    slug: "base",
    name: "Base",
    tagline: "Verified businesses from a raw list.",
    sections: [
      {
        id: "batches",
        label: "Batches",
        items: [
          item("b1", "Boston coffee roasters", "120 rows in", "Verified", ["112 matched to a real site.", "8 left for a person to check."]),
          item("b2", "Cape Town solar installers", "64 rows in", "Running", ["41 verified so far.", "Next step: read each contact page."]),
          item("b3", "Ohio sheet-metal shops", "200 rows in", "Queued", ["Starts when the earlier batches finish."]),
        ],
      },
      {
        id: "skills",
        label: "Skills used",
        items: [
          item("s1", "Find a site", "Free · code and search", "Ready", ["Looks a business up and picks its own site."]),
          item("s2", "Read a page", "Free · our browser", "Ready", ["Pulls name, address and phone from the page."]),
        ],
      },
    ],
  },
  {
    slug: "tiger",
    name: "Tiger",
    tagline: "Watches prices and rival moves.",
    sections: [
      {
        id: "watches",
        label: "Watches",
        items: [
          item("w1", "Rival A — trail shoe, 40 mm", "Checked 2 hours ago", "Changed", ["Price went from $129 to $119.", "Seen on 2 pages."]),
          item("w2", "Rival B — pantry flour", "Checked today", "Steady", ["No change in 14 days."]),
          item("w3", "Rival C — cargo rate, Boston", "Checked yesterday", "Changed", ["Quote up 6% since last month."]),
        ],
      },
      {
        id: "alerts",
        label: "Alerts",
        items: [
          item("a1", "Rival A cut a price", "Today", "New", ["Sent to the owner of the watch."]),
          item("a2", "Rival C raised rates", "Yesterday", "Read", ["Seen by two people."]),
        ],
      },
    ],
  },
  {
    slug: "market-lab",
    name: "Market Lab",
    tagline: "Sourced market research.",
    sections: [
      {
        id: "readings",
        label: "Readings",
        items: [
          item("r1", "Used-truck asking prices, Northeast", "Weekly series", "Up 2.1%", ["Median asking price $38,400.", "Source: 6 dealer feeds."]),
          item("r2", "Solar panel wholesale, EU", "Monthly series", "Down 0.8%", ["Median $0.11 per watt.", "Source: 3 vendor lists."]),
          item("r3", "Lumber futures, nearby month", "Daily series", "Flat", ["Moved under 0.2% this week."]),
        ],
      },
      {
        id: "reports",
        label: "Reports",
        items: [
          item("p1", "Q3 freight outlook", "6 pages · 14 sources", "Ready", ["Every figure links to where it came from."]),
        ],
      },
    ],
  },
  {
    slug: "tisan",
    name: "Tisan",
    tagline: "Sites and apps from a short brief.",
    sections: [
      {
        id: "chat",
        label: "Chat",
        items: [
          item("c1", "Brief: bakery site with online orders", "3 messages", "Draft ready", ["You: A one-page site for a bakery, with an order form.", "Tisan: Draft ready. Menu, hours and form are in place."]),
          item("c2", "Brief: invoice tracker app", "5 messages", "Building", ["You: Track unpaid invoices by client.", "Tisan: Two screens built. Working on reminders."]),
        ],
      },
      {
        id: "gold",
        label: "Gold examples",
        items: [
          item("g1", "Plumber landing page", "Approved example", "Gold", ["Used as a model for new local-service sites."]),
        ],
      },
    ],
  },
  {
    slug: "radix",
    name: "Radix",
    tagline: "Finds what systems and sites expose.",
    sections: [
      {
        id: "findings",
        label: "Findings",
        items: [
          item("f1", "Admin page open to the public", "shop.example.test", "High", ["/admin loads without a sign-in.", "Fix: require a sign-in."]),
          item("f2", "Old software version shown", "api.example.test", "Medium", ["Server header names a version with known problems."]),
          item("f3", "Missing security headers", "www.example.test", "Low", ["Three standard headers are not set."]),
        ],
      },
      {
        id: "reports",
        label: "Reports",
        items: [
          item("p1", "Weekly check, 3 sites", "3 findings", "Ready", ["One high, one medium, one low."]),
        ],
      },
    ],
  },
  {
    slug: "skala",
    name: "Skala",
    tagline: "Tests skills before they are used.",
    sections: [
      {
        id: "skills",
        label: "Skills",
        items: [
          item("k1", "base.find_site 1.1.0", "42 test cases", "Approved", ["Passed 41 of 42. The one miss is logged."]),
          item("k2", "market.mine_prices 0.3.0", "18 test cases", "Testing", ["Passed 14 of 18 so far."]),
          item("k3", "tiger.track_series 1.0.0", "30 test cases", "Needs review", ["Two cases differ from the stored answer."]),
        ],
      },
    ],
  },
  {
    slug: "tank",
    name: "Tank",
    tagline: "Routes each task and keeps receipts.",
    sections: [
      {
        id: "roster",
        label: "Roster",
        items: [
          item("t1", "Base batch step", "Free rung · code", "Done", ["Cost $0.00. Answered from the cache."]),
          item("t2", "Zenas memo draft", "Cheapest paid rung", "Done", ["Cost $0.04. One model call."]),
        ],
      },
      {
        id: "workers",
        label: "Workers",
        items: [
          item("x1", "Queue worker 1", "Idle", "Healthy", ["Last job finished 3 minutes ago."]),
          item("x2", "Queue worker 2", "Busy", "Healthy", ["Running a Base batch."]),
        ],
      },
    ],
  },
];

export function demoProductFor(slug: string | null | undefined): DemoProduct | null {
  return DEMO_PRODUCTS.find((p) => p.slug === slug) ?? null;
}

/** Fixtures are only useful when every section has clickable rows with detail. */
export function demoProductIsFull(product: DemoProduct): boolean {
  return product.sections.length > 0 && product.sections.every((s) => s.items.length > 0 && s.items.every((i) => i.detail.length > 0));
}
