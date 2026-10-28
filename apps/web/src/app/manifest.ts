import type { MetadataRoute } from "next";

// F11-AC1: installable as an app (served as /manifest.webmanifest). Icons: scripts/make_icons.py.
export const THEME_COLOR = "#115e59"; // petrol

export default function manifest(): MetadataRoute.Manifest {
  const icon = (size: number, purpose: "any" | "maskable") => ({
    src: `/icons/icon-${size}${purpose === "maskable" ? "-maskable" : ""}.png`,
    sizes: `${size}x${size}`,
    type: "image/png",
    purpose,
  });
  return {
    name: "Pflege-Posteingang",
    short_name: "Posteingang",
    description: "Bewerbungsdemo: sichere KI für Pflegedokumente (Musterdaten)",
    lang: "de",
    start_url: "/",
    scope: "/",
    display: "standalone",
    theme_color: THEME_COLOR,
    background_color: "#ffffff",
    icons: [icon(192, "any"), icon(512, "any"), icon(192, "maskable"), icon(512, "maskable")],
  };
}
