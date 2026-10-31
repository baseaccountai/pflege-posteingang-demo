import { describe, expect, it } from "vitest";

import { formatDateTime, formatTime, todayInBerlin } from "@/lib/dates";

describe("todayInBerlin", () => {
  it("is the calendar day in Berlin, not in UTC", () => {
    // 23:30 UTC on 27 Oct (winter time from 25 Oct) is already 28 Oct in Berlin.
    expect(todayInBerlin(new Date("2026-10-27T23:30:00Z"))).toBe("2026-10-28");
    expect(todayInBerlin(new Date("2026-10-27T22:30:00Z"))).toBe("2026-10-27");
  });
});

describe("formatDateTime", () => {
  it("shows day and time in Berlin, to the second (F12: when did it happen)", () => {
    expect(formatDateTime("2026-10-30T13:05:09.123+00:00")).toBe("30.10.2026, 14:05:09");
  });
});

describe("formatTime", () => {
  it("is the time of day in Berlin, also across midnight and in summer time", () => {
    expect(formatTime("2026-10-31T23:15:00+00:00")).toBe("00:15");
    expect(formatTime("2026-07-01T10:05:00Z")).toBe("12:05");
  });
});
