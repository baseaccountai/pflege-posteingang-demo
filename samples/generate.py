"""Generates the sample documents in samples/ (F10-AC2, F10-AC3).

    make samples        (writes into samples/; same bytes on every run)

Everything is invented: people, practices and places come only from the fixed lists below.
Every page carries a diagonal "MUSTER" watermark. The output is reproducible (same bytes on
every run), so the files can be committed and checked.

Besides the documents it writes samples/ocr/<file>.md: the text an OCR should read. The
OCR stand-in (OCR_PROVIDER=fake) uses it in the end-to-end tests, so every sample - also
the four bad ones - "reads" like the real thing would.
"""

import io
import sys
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.colors import Color, black
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

# --- The only names allowed in sample documents (F10-AC3) ----------------------------------
RESIDENTS = {  # same people as the seed (supabase/seed), all invented
    "wb1": ["Hr. Muster-Bauer", "Fr. Beispiel", "Hr. Probe"],
    "wb2": ["Fr. Testfeld", "Hr. Exempel", "Fr. Vorlage"],
}
DOCTORS = ["Dr. med. Lorem", "Dr. med. Ipsum", "Dr. Dolor"]
ALLOWED_NAMES = ["Muster-Bauer", "Beispiel", "Probe", "Testfeld", "Exempel", "Vorlage"] + [
    "Lorem",
    "Ipsum",
    "Dolor",
]
ALLOWED_PLACES = ["Klinikum Musterstadt", "Hausarztpraxis Dr. Ipsum", "Pflegeheim Haus Beispielhof"]
PLACES = list(ALLOWED_PLACES)

# Medication of Hr. Muster-Bauer in the record (seed) and in the newer plan: one new,
# one stopped, one changed - so the comparison (F03-AC7) has something to show.
RECORD_MEDICATIONS = [
    {"name": "Ramipril", "strength": "5 mg", "dosage": "1-0-0-0"},
    {"name": "Metformin", "strength": "500 mg", "dosage": "1-0-1-0"},
    {"name": "Simvastatin", "strength": "20 mg", "dosage": "0-0-1-0"},
]
PLAN_MEDICATIONS = [
    {"name": "Ramipril", "strength": "5 mg", "dosage": "1-0-0-0"},
    {"name": "Metformin", "strength": "1000 mg", "dosage": "1-0-1-0"},
    {"name": "Torasemid", "strength": "10 mg", "dosage": "1-0-0-0"},
]


def med_rows(meds: list[dict]) -> list[str]:
    return [f"| {m['name']} | {m['strength']} | {m['dosage']} |" for m in meds]


TABLE_HEAD = ["| Medikament | Stärke | Dosierung (mo-mi-ab-na) |", "|---|---|---|"]

# Each document: lines of Markdown. The PDF shows them as text; the .md is the OCR answer.
ARZTBRIEF = [
    "# Entlassungsbrief",
    "Klinikum Musterstadt, Innere Medizin, 20.10.2026",
    "Patient: Hr. Muster-Bauer, geb. 03.04.1941, Pflegeheim Haus Beispielhof",
    "Behandelnder Arzt: Dr. med. Lorem",
    "## Diagnosen",
    "- Herzinsuffizienz NYHA II",
    "- Diabetes mellitus Typ 2",
    "## Medikation bei Entlassung",
    *TABLE_HEAD,
    *med_rows(PLAN_MEDICATIONS),
    "## Empfehlungen",
    "Kontrolle Kreatinin und Kalium in 2 Wochen beim Hausarzt.",
    "Gewicht täglich messen, Zunahme über 2 kg in 3 Tagen bitte melden.",
]
MEDIKATIONSPLAN = [
    "# Medikationsplan",
    "Hausarztpraxis Dr. Ipsum, Stand 22.10.2026",
    "Für: Hr. Muster-Bauer, Pflegeheim Haus Beispielhof",
    *TABLE_HEAD,
    *med_rows(PLAN_MEDICATIONS),
    "Hinweis: Simvastatin abgesetzt. Metformin Dosis erhöht.",
]
UEBERLEITUNGSBOGEN = [
    "# Pflegeüberleitungsbogen",
    "Klinikum Musterstadt an Pflegeheim Haus Beispielhof, 24.10.2026",
    "Bewohnerin: Fr. Testfeld, geb. 12.09.1938",
    "## Pflegerische Situation",
    "Mobilität: mit Rollator, Sturzgefahr. Ernährung: selbstständig, Diabeteskost.",
    "Wundversorgung: Dekubitus Grad 1 Ferse links, Lagerung alle 3 Stunden.",
    "## Medikation",
    *TABLE_HEAD,
    "| Bisoprolol | 2,5 mg | 1-0-0-0 |",
    "| Pantoprazol | 20 mg | 1-0-0-0 |",
    "Wiedervorlage: Wundkontrolle am 31.10.2026 durch Dr. Dolor.",
]
KOCHREZEPT = [
    "# Omas Apfelkuchen",
    "Zutaten: 500 g Mehl, 250 g Butter, 200 g Zucker, 4 Eier, 1 kg Äpfel.",
    "Den Teig kneten und eine Stunde kalt stellen.",
    "Äpfel schälen, in Spalten schneiden und auf dem Teig verteilen.",
    "Bei 180 Grad etwa 45 Minuten backen.",
]

WATERMARK = "MUSTER"


def plain(line: str) -> str:
    """A Markdown line as it is printed on the page."""
    return line.lstrip("#- ").replace("|", "   ").strip()


# --- PDF ------------------------------------------------------------------------------------
def write_pdf(path: Path, lines: list[str]) -> None:
    # invariant=1: no creation date or random id, so every run gives the same bytes.
    canvas = Canvas(str(path), pagesize=A4, invariant=1)
    width, height = A4
    y = height - 72
    for line in lines:
        if line.startswith("|---"):
            continue
        size = 16 if line.startswith("# ") else 13 if line.startswith("## ") else 11
        canvas.setFont("Helvetica-Bold" if line.startswith("#") else "Helvetica", size)
        canvas.drawString(60, y, plain(line))
        y -= size + 9
    canvas.saveState()
    canvas.setFillColor(Color(0.8, 0.1, 0.1, alpha=0.18))
    canvas.setFont("Helvetica-Bold", 110)
    canvas.translate(width / 2, height / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, -40, WATERMARK)
    canvas.restoreState()
    canvas.setFillColor(black)
    canvas.showPage()
    canvas.save()


# --- Images ---------------------------------------------------------------------------------
# Bitstream Vera ships with reportlab (pinned version): umlauts included, same font on every
# machine. Pillow's built-in default font has no umlauts.
VERA = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"


def image_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(VERA), size)


def page_image(lines: list[str], width: int = 2480, height: int = 3508) -> Image.Image:
    """A4 at 300 dpi, like a phone photo of a page."""
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    y = 200
    for line in lines:
        if line.startswith("|---"):
            continue
        size = 70 if line.startswith("# ") else 52 if line.startswith("## ") else 44
        draw.text((170, y), plain(line), fill="black", font=image_font(size))
        y += int(size * 1.6)
    return add_watermark(image)


def add_watermark(image: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = image_font(image.width // 5)
    left, top, right, bottom = draw.textbbox((0, 0), WATERMARK, font=font)
    x = (image.width - (right - left)) // 2
    y = (image.height - (bottom - top)) // 2
    draw.text((x, y), WATERMARK, fill=(200, 30, 30, 60), font=font)
    layer = layer.rotate(45, center=(image.width // 2, image.height // 2))
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


def write_jpeg(path: Path, image: Image.Image, quality: int = 70) -> None:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True)
    path.write_bytes(buffer.getvalue())


def write_ocr(target: Path, relative: str, text: str) -> None:
    (target / "ocr" / f"{relative.replace('/', '__')}.md").write_text(text, encoding="utf-8")


def generate(target: Path) -> None:
    (target / "bad").mkdir(parents=True, exist_ok=True)
    (target / "ocr").mkdir(exist_ok=True)
    documents = {
        "arztbrief_muster-bauer.pdf": ARZTBRIEF,
        "medikationsplan_muster-bauer.pdf": MEDIKATIONSPLAN,
        "ueberleitungsbogen_testfeld.pdf": UEBERLEITUNGSBOGEN,
        "bad/kochrezept.pdf": KOCHREZEPT,
    }
    for relative, lines in documents.items():
        write_pdf(target / relative, lines)
        write_ocr(target, relative, "\n".join(lines))

    photo = page_image(ARZTBRIEF)
    write_jpeg(target / "arztbrief_muster-bauer_foto.jpg", photo)
    write_ocr(target, "arztbrief_muster-bauer_foto.jpg", "\n".join(ARZTBRIEF))

    # The bad cases (F02-AC7): what a careless photo gives the OCR.
    blank = add_watermark(Image.new("RGB", (1240, 1754), "white"))
    write_jpeg(target / "bad/leere_seite.jpg", blank)
    write_ocr(target, "bad/leere_seite.jpg", "")
    small = photo.resize((1240, 1754))
    write_jpeg(target / "bad/unscharf.jpg", small.filter(ImageFilter.GaussianBlur(14)))
    write_ocr(target, "bad/unscharf.jpg", "Ent ss ngsb ief\nK in kum M s er")
    tilted = small.rotate(28, expand=True, fillcolor=(90, 90, 90)).crop((0, 0, 1500, 900))
    write_jpeg(target / "bad/schief.jpg", tilted)
    write_ocr(target, "bad/schief.jpg", "# Entlassungsbrief\nKlinikum Muster")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    generate(out)
    print(f"Musterdokumente geschrieben nach {out}")
