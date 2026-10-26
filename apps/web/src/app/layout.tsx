import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { Suspense } from "react";

import { DemoBanner } from "@/components/demo-banner";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { currentSession } from "@/lib/auth/current";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Pflege-Posteingang",
  description: "Bewerbungsdemo: sichere KI für Pflegedokumente (Musterdaten)",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="de"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <DemoBanner />
        <Suspense fallback={<SiteHeader />}>
          <SessionHeader />
        </Suspense>
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}

async function SessionHeader() {
  const state = await currentSession();
  return <SiteHeader roleLabel={state.kind === "active" ? state.session.displayName : null} />;
}
