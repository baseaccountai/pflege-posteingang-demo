// F09-AC3, AC4: the requirements of the job ad and where the demo shows them - a list on
// the phone, a grid on wider screens. Data: content/requirements-map.ts.
import Link from "next/link";

import { REQUIREMENTS, repoHref } from "@/content/requirements-map";

const LEVEL = { gefordert: "gefordert", wuenschenswert: "wünschenswert" } as const;

export function RequirementsMap() {
  return (
    <section aria-labelledby="requirements-heading" className="flex flex-col gap-3">
      <h2 id="requirements-heading" className="text-lg font-semibold">
        Anforderungen der Stelle – und wo sie hier umgesetzt sind
      </h2>
      <ul className="grid gap-3 md:grid-cols-2">
        {REQUIREMENTS.map((entry) => (
          <li
            key={entry.id}
            data-requirement={entry.id}
            data-testid={`requirement-${entry.id}`}
            className="flex flex-col gap-2 rounded-lg border p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h3 className="font-semibold">{entry.text}</h3>
              <span
                className={
                  entry.level === "gefordert"
                    ? "rounded bg-teal-100 px-1.5 py-0.5 text-xs text-teal-900"
                    : "rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800"
                }
              >
                {LEVEL[entry.level]}
              </span>
            </div>
            <p className="text-sm">{entry.how}</p>
            <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              {entry.status === "stufe2" ? (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">in Arbeit (Stufe 2)</span>
              ) : (
                entry.appHref && (
                  <Link href={entry.appHref} className="font-medium underline">
                    In der App: {entry.appLabel}
                  </Link>
                )
              )}
              {entry.repoPaths.map((repoPath) => (
                <a
                  key={repoPath}
                  href={repoHref(repoPath)}
                  target="_blank"
                  rel="noopener"
                  className="text-muted-foreground font-mono text-xs underline"
                >
                  {repoPath}
                </a>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
