# Kick-off-Prompt

> Diesen Text in eine neue Claude-Code-Sitzung im Projektordner einfügen.

---

Wir bauen gemeinsam meine Bewerbungs-Demo **„Pflege-Posteingang“** für die Stelle Nr. 479 (Wissenschaftlicher Mitarbeiter Web Engineering, Hochschule Anhalt, Projekt KLARA). Bewerbungsfrist ist der **11.11.2026**; Stufe 1 soll am **02.11.2026** öffentlich erreichbar sein.

**Lies zuerst vollständig:**
1. `docs/superpowers/specs/2026-10-23-pflege-posteingang-demo-design.md` – das freigegebene Design (Was und Warum).
2. `docs/superpowers/plans/2026-10-23-pflege-posteingang-demo.md` – der Umsetzungsplan (Phasen 0–9, Phase 0 im Detail).
3. `CLAUDE.md`, sobald es existiert.

**Arbeitsweise (verbindlich):**
- Setze den Plan mit dem Skill **superpowers:executing-plans** um, Task für Task, Checkboxen im Plan abhaken.
- **Spec-getrieben:** Kein Feature-Code ohne von mir freigegebene Spec unter `docs/specs/Fxx-<name>/` (`requirements.md` mit EARS-Kriterien `Fxx-ACn`, `design.md`, `tasks.md`).
- **Testgetrieben** (superpowers:test-driven-development): erst Test, Fehlschlag zeigen, dann Code, dann grün.
- **Halte-Punkt nach jeder Phase:** (1) alle Tests grün, Ausgabe zeigen; (2) **Codex-Review** des Phasenstands über das installierte Codex-Plugin; (3) Befunde kritisch bewerten (superpowers:receiving-code-review) und berechtigte umsetzen; (4) kurze Zusammenfassung: gebaut / Codex-Befunde / umgesetzt / offen; (5) **anhalten und mich fragen, ob es weitergeht.**
- Bei Zeitnot zuerst den vollständigen lokalen Betrieb reduzieren, nie die Sicherheitsfeatures. Sag es mir, bevor du etwas streichst.
- Nur **Musterdaten**; niemals echte Personendaten, niemals Schlüssel im Repo.
- Kommunikation mit mir auf **Deutsch**, gern mit Tabellen. Code, Bezeichner und Commits auf Englisch.
- Wenn du etwas entscheiden musst, das nicht im Design oder Plan steht: kleine Dinge selbst entscheiden und im Phasenbericht nennen; alles, was ändert, *was* gebaut wird, vorher mich fragen.
- Konten (Supabase, Zitadel, Mistral, Koyeb, Vercel, GitHub) lege ich selbst an – führe mich Schritt für Schritt durch und prüfe danach.

**Starte jetzt mit Phase 0, Task 0.1.** Gib mir zuerst in 3–5 Zeilen wieder, was du in Phase 0 vorhast, dann leg los.
