// Stand-in for the FastAPI app in the notice tests (F10-AC12, AC7, AC13): a sleeping,
// slow, limited or resetting API on demand. A second `next start` points at it, so the
// real API of the other tests is never disturbed. The behaviour depends only on the path
// (resident id prefix), so parallel tests (desktop + mobile) do not get in each other's way.
//
//   GET  /residents/51000000-…/record   answers after 7 s (longer than the 5 s timeout)
//   GET  /residents/50300000-…/record   503 on the first call per id, then the record
//   POST /documents                     429 daily_quota
//   POST /follow-ups/{id}/done          503 maintenance (nightly reset)
import http from "node:http";

const port = Number(process.argv[2]);
const DAILY_QUOTA = "Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter.";
const MAINTENANCE = "Demo wird gerade zurückgesetzt – bitte in einer Minute erneut versuchen";
const seen = new Map();

const provenance = {
  document_id: null,
  doc_type: null,
  document_date: null,
  actor_type: "human",
  confirmed_by_name: "Pflegekraft WB1",
  confirmed_at: "2026-10-20T08:00:00Z",
};

function record(id) {
  return {
    resident: { id, ward_id: "wb1", ward_name: "WB 1", display_name: "Fr. Attrappe", room: "101" },
    medications: { active: [], discontinued: [] },
    diagnoses: [],
    follow_ups: [
      {
        id: "f0000000-0000-0000-0000-000000000001",
        title: "Blutdruck messen",
        due_date: null,
        status: "open",
        overdue: false,
        done_by_name: null,
        done_at: null,
        provenance,
      },
    ],
    documents: [],
  };
}

function send(response, status, body) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

http
  .createServer((request, response) => {
    const { pathname } = new URL(request.url, "http://stub");
    const get = request.method === "GET";
    const recordMatch = pathname.match(/^\/residents\/([0-9a-f-]+)\/record$/);
    if (get && pathname === "/health") return send(response, 200, { status: "ok" });
    if (get && pathname === "/health/ready") return send(response, 200, { db: "ok" });
    if (get && pathname === "/documents") return send(response, 200, []);
    if (get && recordMatch) {
      const id = recordMatch[1];
      if (id.startsWith("51000000")) return setTimeout(() => send(response, 200, record(id)), 7000);
      if (id.startsWith("50300000")) {
        const calls = (seen.get(id) ?? 0) + 1;
        seen.set(id, calls);
        if (calls === 1) return send(response, 503, { detail: "starting" });
      }
      return send(response, 200, record(id));
    }
    if (request.method === "POST" && pathname === "/documents") {
      request.resume();
      return send(response, 429, { error_code: "daily_quota", message: DAILY_QUOTA });
    }
    if (request.method === "POST" && /^\/follow-ups\/[^/]+\/done$/.test(pathname)) {
      return send(response, 503, { error_code: "maintenance", message: MAINTENANCE });
    }
    return send(response, 404, { detail: "Nicht gefunden" });
  })
  .listen(port, "127.0.0.1");
