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
