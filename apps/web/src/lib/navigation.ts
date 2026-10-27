// Full page loads on purpose, not client routing: no client cache keeps data of a previous
// session or of a document that has just been approved (F01-AC13, F01-AC21).

export function goTo(path: string) {
  window.location.assign(path);
}

export function leaveEndedSession() {
  goTo("/?sitzung=abgelaufen");
}
