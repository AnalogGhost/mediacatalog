from pathlib import Path

from pypdf import PdfReader, PdfWriter


def merge_pdfs(pdf_paths, output_path):
    writer = PdfWriter()
    for path in pdf_paths:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as handle:
        writer.write(handle)
