// Where an original document opens: live through the BFF (F04-AC10, needs a session),
// in the sample record as a static copy of the seed file (F10-AC14, no login, no API).

export const documentFileHref = (documentId: string) =>
  `/api/documents/${encodeURIComponent(documentId)}/file`;

export const sampleFileHref = (documentId: string) => `/muster/${encodeURIComponent(documentId)}.pdf`;

export const fileHref = (documentId: string, sample = false) =>
  sample ? sampleFileHref(documentId) : documentFileHref(documentId);
