import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { DemoBanner } from "@/components/demo-banner";
import { SiteFooter } from "@/components/site-footer";
import { SessionSync } from "@/components/session-sync";
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
      {/* pb-16: room for the bottom navigation on the phone (F11-AC4). */}
      <body className="min-h-full flex flex-col pb-16 md:pb-0">
        <DemoBanner />
        <SessionSync />
        <Suspense fallback={<SiteHeader />}>
          <SessionHeader />
        </Suspense>
        <div className="flex flex-1 flex-col md:flex-row">
          <Suspense fallback={null}>
            <SessionNav />
          </Suspense>
          <div className="flex min-w-0 flex-1 flex-col">{children}</div>
        </div>
        <SiteFooter />
      </body>
    </html>
  );
}

async function SessionHeader() {
  const state = await currentSession();
  return <SiteHeader roleLabel={state.kind === "active" ? state.session.displayName : null} />;
}

/** The main navigation only for a signed-in user (the areas need a session). */
async function SessionNav() {
  const state = await currentSession();
  return state.kind === "active" ? <AppNav /> : null;
}
