// F10-AC14: the sample record from the repo file, moved to today. No fetch, no session:
// it works while the API sleeps (link from the start-up notice, F10-AC13).
import { connection } from "next/server";

import { ResidentRecordView } from "@/components/resident-record";
import { todayInBerlin } from "@/lib/dates";
import { sampleRecord } from "@/lib/sample-record";

export async function SampleRecordSection() {
  // "Today" is read per request, not frozen at build time.
  await connection();
  return <ResidentRecordView record={sampleRecord(todayInBerlin())} sample />;
}
