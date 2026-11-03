// Offline smoke only: fixed loopback origin, no redirects or remote imports.
import http from "k6/http";
import { sleep } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const origin = __ENV.TISAN_CHECK_ORIGIN;
if (!/^http:\/\/127\.0\.0\.1:[1-9][0-9]*$/.test(origin))
  throw new Error("loopback origin required");
const paths = JSON.parse(__ENV.TISAN_CHECK_PAGES);
if (!Array.isArray(paths) || !paths.length || paths.some((path) =>
  typeof path !== "string" || !path.startsWith("/") || path.startsWith("//") || /[\\\u0000-\u0020\u007f?#{},]/.test(path)))
  throw new Error("local page paths required");
const pageOk = new Rate("page_ok");
const pageTime = new Trend("page_time", true);
const pageRequests = new Counter("page_requests");
const thresholds = {};
for (const path of paths) {
  thresholds[`page_ok{page:${path}}`] = ["rate==1"];
  thresholds[`page_time{page:${path}}`] = ["p(95)>=0"];
  thresholds[`page_requests{page:${path}}`] = ["count>0"];
}
export const options = {
  vus: 3,
  duration: "3s",
  gracefulStop: "3s",
  maxRedirects: 0,
  discardResponseBodies: true,
  thresholds,
  summaryTrendStats: ["p(95)"],
};
export default function () {
  for (const path of paths) {
    const response = http.get(origin + path, { redirects: 0, timeout: "2s", tags: { page: path } });
    pageOk.add(response.status === 200, { page: path });
    pageTime.add(response.timings.duration, { page: path });
    pageRequests.add(1, { page: path });
  }
  sleep(0.2);
}
export function handleSummary(data) {
  const pages = paths.map((page) => {
    const status = data.metrics[`page_ok{page:${page}}`]?.values;
    const requests = data.metrics[`page_requests{page:${page}}`]?.values?.count || 0;
    const p95_ms = data.metrics[`page_time{page:${page}}`]?.values?.["p(95)"];
    return { page, ok: requests > 0 && status?.rate === 1, status: status?.rate === 1 ? 200 : null,
      requests, failures: status?.fails ?? requests, p95_ms: p95_ms ?? null };
  });
  return { ".k6-check.json": JSON.stringify({ name: "k6", ok: pages.every((row) => row.ok), pages }) };
}
