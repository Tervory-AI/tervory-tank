import { presentFeeds, presentMatters, presentReview, releasedOnly, reviewerMay } from "../workspace/app/api/zenas/rules.ts";

const rawDocs = [
  { id: "1", state: "draft", body: "hidden draft", kind: "draft", version: 1 },
  { id: "2", state: "in_review", body: "still hidden", kind: "memo", version: 2 },
  { id: "3", state: "released", body: "the client may read this", kind: "memo", version: 3, sources: [] },
];
const docs = releasedOnly(rawDocs);
if (docs.length !== 1 || docs[0].body !== "the client may read this") {
  throw new Error("unreleased documents must stay hidden");
}

const matters = presentMatters({
  matters: [{ id: "m", title: "Supply", jurisdiction: "za", area: "contracts", status: "open", documents: rawDocs }],
});
if (matters[0].documents.length !== 1 || matters[0].documents[0].id !== "3") {
  throw new Error("a matter shows only released documents");
}

if (reviewerMay(["us"], "za")) throw new Error("a US reviewer cannot sign South African work");
if (!reviewerMay(["za"], "za")) throw new Error("a ZA reviewer can sign South African work");
if (!reviewerMay(["us", "za"], "both")) throw new Error("either tag can sign work in both");

const review = presentReview({
  items: [
    {
      document: { id: "d1", body: "clause", state: "in_review", sources: [{ citation: "s 1", quote: "words" }] },
      matter: { id: "m1", title: "NDA", jurisdiction: "za", area: "contracts" },
      matches: [{ id: "w1", outcome: "enforced", jurisdiction: "za", element_findings: [{ element: "offer", finding: "met" }] }],
    },
    {
      document: { id: "d2", body: "other", state: "in_review", sources: [] },
      matter: { id: "m2", title: "US supply", jurisdiction: "us", area: "contracts" },
      matches: [],
    },
  ],
}, ["za"]);
if (review.length !== 1 || review[0].documentId !== "d1") throw new Error("review list must follow the jurisdiction tag");
if (review[0].sources[0].citation !== "s 1") throw new Error("sources must stay beside the draft");
if (review[0].matches[0].findings[0] !== "offer: met") throw new Error("worked matters must be shown");

const feeds = presentFeeds({
  region: "za",
  sources: [{
    source_id: "laws-africa",
    name: "Laws.Africa",
    key_name: "LAWS_AFRICA_API_TOKEN",
    key_set: true,
    api_key: "do-not-show",
    documents: 12,
    last_update: "2026-10-14T00:00:00Z",
    errors: ["token sk-live-secret failed"],
  }],
});
const encoded = JSON.stringify(feeds);
if (encoded.includes("do-not-show") || encoded.includes("sk-live-secret")) {
  throw new Error("a feed must not show a key value");
}
if (feeds.sources[0].key_name !== "LAWS_AFRICA_API_TOKEN" || feeds.sources[0].key_set !== "yes") {
  throw new Error("key name and whether it is set must remain");
}
if (!feeds.sources[0].errors[0].includes("reported an error")) throw new Error("secret-looking errors must be replaced");

console.log("ok");
