// Phase 9: docs/projektbeschreibung.md is written for GitHub - its links are relative to
// docs/. In the app the same text points into the repository on GitHub, and its pictures
// are the copies in public/projekt/ (written by `make project-description`).
import { repoHref } from "@/content/requirements-map";

const PICTURES = "assets/projekt/";

/** Link target in the app: web addresses and anchors stay, repository paths go to GitHub. */
export function descriptionHref(href: string | undefined): string | undefined {
  if (!href) return undefined;
  if (/^[a-z]+:/i.test(href) || href.startsWith("#") || href.startsWith("/")) return href;
  const [file, anchor] = href.split("#");
  // Resolve against docs/ (URL does the "../" for us); keep a trailing "/" for folders.
  const repoPath = new URL(file, "https://repo.invalid/docs/").pathname.slice(1);
  return repoHref(decodeURI(repoPath)) + (anchor ? `#${anchor}` : "");
}

/** Picture source in the app: only the copied pictures of the description, nothing else. */
export function descriptionImage(src: string | undefined): string | undefined {
  if (!src?.startsWith(PICTURES)) return undefined;
  const name = src.slice(PICTURES.length);
  return /^[\w.-]+$/.test(name) && !name.includes("..") ? `/projekt/${name}` : undefined;
}
