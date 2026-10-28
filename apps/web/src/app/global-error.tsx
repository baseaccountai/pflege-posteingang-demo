"use client";
// Error in the root layout itself: Next.js then replaces the whole document, so this page
// brings <html>, banner and footer itself (F10-AC4).
import "./globals.css";

import { DemoBanner } from "@/components/demo-banner";
import { ErrorMessage } from "@/components/error-message";
import { SiteFooter } from "@/components/site-footer";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="de" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <DemoBanner />
        <ErrorMessage reset={reset} />
        <SiteFooter />
      </body>
    </html>
  );
}
