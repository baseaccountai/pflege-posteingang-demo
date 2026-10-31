// Dates as the care home sees them: German format, Berlin time, whatever the server's zone.

const DAY = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Europe/Berlin",
});

/** "2026-10-12" (a calendar date, no time zone) → "12.10.2026". */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-");
  return `${day}.${month}.${year}`;
}

/** A point in time (ISO with zone) → its day in Berlin, "25.10.2026". */
export function formatDay(isoTimestamp: string): string {
  return DAY.format(new Date(isoTimestamp));
}

const ISO_DAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" });

/** The current day in Berlin as "2026-10-28" (en-CA formats dates as ISO). */
export function todayInBerlin(now: Date = new Date()): string {
  return ISO_DAY.format(now);
}

const DATE_TIME = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  timeZone: "Europe/Berlin",
});

/** A point in time → "30.10.2026, 14:05:09" in Berlin (the audit log, F12). */
export function formatDateTime(isoTimestamp: string): string {
  return DATE_TIME.format(new Date(isoTimestamp));
}

const TIME = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });

/** A point in time → "00:15" in Berlin (how long an agent's proposal is valid, F08-AC5). */
export function formatTime(isoTimestamp: string): string {
  return TIME.format(new Date(isoTimestamp));
}
