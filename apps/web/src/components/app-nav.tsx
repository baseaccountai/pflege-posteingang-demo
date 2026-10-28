"use client";
// F11-AC4: the four areas of the app - at the bottom on the phone (thumb reach), as a side
// bar from 768 px on. The current area is marked (aria-current). Shown when signed in.
import { House, Inbox, MessageCircleQuestion, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const AREAS = [
  { href: "/", label: "Start", icon: House },
  { href: "/posteingang", label: "Posteingang", icon: Inbox },
  { href: "/bewohner", label: "Bewohner", icon: Users },
  { href: "/fragen", label: "Fragen", icon: MessageCircleQuestion },
];

const isCurrent = (href: string, path: string) => (href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`));

export function AppNav() {
  const path = usePathname();
  return (
    <nav
      aria-label="Hauptnavigation"
      className="bg-background fixed inset-x-0 bottom-0 z-20 border-t md:sticky md:top-0 md:h-fit md:w-48 md:shrink-0 md:border-t-0 md:border-r"
    >
      <ul className="flex justify-around md:flex-col md:gap-1 md:p-3">
        {AREAS.map(({ href, label, icon: Icon }) => {
          const current = isCurrent(href, path);
          return (
            <li key={href} className="flex-1 md:flex-none">
              <Link
                href={href}
                aria-current={current ? "page" : undefined}
                className={`flex flex-col items-center gap-0.5 px-2 py-2 text-xs md:flex-row md:gap-2 md:rounded-md md:text-sm ${
                  current ? "font-semibold text-teal-800 md:bg-teal-50" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon aria-hidden className="size-5 md:size-4" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
