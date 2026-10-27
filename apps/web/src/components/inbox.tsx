"use client";
// Screen 2: upload card + live inbox list sharing one list of documents.
import { useCallback, useState } from "react";

import { InboxList, type InboxDocument } from "@/components/inbox-list";
import { UploadCard } from "@/components/upload-card";
import { leaveEndedSession } from "@/lib/navigation";

export function Inbox({ initial, wards }: { initial: InboxDocument[]; wards?: string[] }) {
  const [documents, setDocuments] = useState(initial);
  const refresh = useCallback(async () => {
    const response = await fetch("/api/documents", { cache: "no-store" });
    if (response.status === 401) leaveEndedSession();
    else if (response.ok) setDocuments(await response.json());
  }, []);
  return (
    <div className="flex flex-col gap-4">
      <UploadCard wards={wards} onUploaded={refresh} />
      <InboxList documents={documents} onChange={setDocuments} />
    </div>
  );
}
