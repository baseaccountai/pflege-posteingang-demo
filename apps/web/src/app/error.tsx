"use client";
// Unexpected error inside a page (F10-AC4): shown within the root layout, so banner and
// footer stay.
import { ErrorMessage } from "@/components/error-message";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorMessage reset={reset} />;
}
