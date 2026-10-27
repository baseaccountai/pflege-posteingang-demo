// Leaving a page whose session ended: a full page load on purpose, not client routing, so
// no client cache keeps data of the previous session (F01-AC13, F01-AC21).
export function leaveEndedSession() {
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- see above
  window.location.assign("/?sitzung=abgelaufen");
}
