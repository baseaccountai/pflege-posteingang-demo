# Testkorpus Prompt-Injection (F13)

Misst die Schutzschichten aus F07; liegt getrennt von den Regeln in
`apps/api/app/security/patterns/` (F07-AC13). Erst wird der Korpus eingetragen, dann
gemessen – Regeln werden nie an den Korpus angepasst.

| Datei | Inhalt | Quelle | Lizenz |
|---|---|---|---|
| `deepset.jsonl` | 77 Angriffe (46 deutsch, 31 englisch) | [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections), Revision `4f61ecb038e9c3fb77e21034b22511b523772cdd` | Apache-2.0, siehe `LICENSE-deepset-Apache-2.0.txt` |
| `bipia_style.jsonl` | 25 indirekte Angriffe in Pflegedokumenten | eigene Einträge, angelehnt an BIPIA (Yi et al. 2023) und Greshake et al. 2023 | eigene Einträge |
| `pflege.jsonl` | 32 Pflege-Angriffe (Datenabfluss, Dosis, Agent, versteckte Schrift) | eigene Einträge | eigene Einträge |
| `benign_pflege.jsonl` | 62 harmlose Pflegetexte, auch solche, die Regeln reizen | eigene Einträge | eigene Einträge |

## Änderungen am deepset-Datensatz (Apache-2.0 §4b)

- Nur Einträge mit Label 1 (Injection) übernommen, als JSON Lines mit eigenen Feldern
  `id`, `lang`, `category` (eigene Zuordnung), `source`, `license`.
- Auswahl: Einträge mit Hassrede, beleidigendem oder vulgärem Inhalt, parteipolitischen
  Botschaften oder Bezug auf reale Personen sind weggelassen – der Korpus ist Teil eines
  öffentlichen Bewerbungs-Repositorys.
- Texte selbst unverändert.

`category = hidden_instruction` bezeichnet Text, der im Originaldokument versteckt wäre
(weiße oder winzige Schrift). Hier wird nur der Text gemessen; das Erkennen der
Verstecktheit prüfen die Szenario-Tests mit den präparierten PDFs.
