// Phase 9: the project description (docs/projektbeschreibung.md, copied into the app) as a
// page. react-markdown never renders raw HTML from the text, so the page stays under the
// strict CSP; links into the repository go to GitHub, pictures come only from public/projekt/.
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { PROJECT_DESCRIPTION } from "@/content/project-description";
import { descriptionHref, descriptionImage } from "@/lib/project-description";

const COMPONENTS: Components = {
  // The page has its own h1 ("Über das Projekt"); the title of the file is for GitHub.
  h1: () => null,
  h2: ({ children }) => <h2 className="mt-6 text-xl font-semibold">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-3 font-semibold">{children}</h3>,
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="ml-5 list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="ml-5 list-decimal space-y-1">{children}</ol>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-teal-300 bg-teal-50 px-3 py-2 text-teal-950">{children}</blockquote>
  ),
  a: ({ href, children }) => {
    const target = descriptionHref(href);
    const external = target !== undefined && /^https?:/.test(target);
    return (
      <a href={target} className="underline" {...(external ? { target: "_blank", rel: "noopener" } : {})}>
        {children}
      </a>
    );
  },
  img: ({ src, alt }) => {
    const source = descriptionImage(typeof src === "string" ? src : undefined);
    if (!source) return <span>{alt}</span>;
    // eslint-disable-next-line @next/next/no-img-element -- static screenshots, sizes vary
    return <img src={source} alt={alt ?? ""} loading="lazy" className="my-2 max-h-[32rem] w-auto rounded-md border" />;
  },
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b py-1 pr-3 align-bottom font-semibold">{children}</th>,
  td: ({ children }) => <td className="border-b py-1 pr-3 align-top">{children}</td>,
  code: ({ children }) => <code className="rounded bg-muted px-1 text-[0.9em]">{children}</code>,
  pre: ({ children }) => <pre className="overflow-x-auto rounded-md bg-muted p-3 text-sm [&_code]:bg-transparent">{children}</pre>,
};

export function ProjectDescription() {
  return (
    <article className="flex flex-col gap-3">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {PROJECT_DESCRIPTION}
      </ReactMarkdown>
    </article>
  );
}
