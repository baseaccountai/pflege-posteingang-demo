import { describe, expect, it } from "vitest";

import { todayInBerlin } from "@/lib/dates";

describe("todayInBerlin", () => {
  it("is the calendar day in Berlin, not in UTC", () => {
    // 23:30 UTC on 27 Oct (winter time from 25 Oct) is already 28 Oct in Berlin.
    expect(todayInBerlin(new Date("2026-10-27T23:30:00Z"))).toBe("2026-10-28");
    expect(todayInBerlin(new Date("2026-10-27T22:30:00Z"))).toBe("2026-10-27");
  });
});
