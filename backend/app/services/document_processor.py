import fitz  # PyMuPDF
import base64
from pathlib import Path
from typing import Literal
import logging

logger = logging.getLogger(__name__)

MAX_PAGES_PER_BATCH = 20   # Claude's vision context handles this comfortably
SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg"}
SUPPORTED_PDF_EXT = {".pdf"}


class DocumentProcessor:
    """
    Converts an uploaded file (PDF or image) into a list of base64-encoded
    page images, which get sent directly to Claude's vision input.

    This handles scanned PDFs, native PDFs, and standalone images the
    same way — as images — so the Document Analysis Agent never has to
    branch its logic based on file type.
    """

    def detect_file_type(self, file_path: str) -> Literal["pdf", "image"]:
        ext = Path(file_path).suffix.lower()
        if ext in SUPPORTED_PDF_EXT:
            return "pdf"
        if ext in SUPPORTED_IMAGE_EXT:
            return "image"
        raise ValueError(f"Unsupported file type: {ext}")

    def pdf_to_page_images(
        self, file_path: str, dpi: int = 150
    ) -> list[dict]:
        """
        Render each PDF page as a base64 PNG image.
        Returns: [{"page_number": 1, "base64": "...", "media_type": "image/png"}, ...]

        Rendering as images (rather than extracting text) is deliberate —
        it lets Claude read tables, charts, and scanned pages the same way
        it reads native text, with no separate OCR step required.
        """
        doc = fitz.open(file_path)
        pages = []

        zoom = dpi / 72  # PDF default is 72 DPI
        matrix = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("utf-8")

            pages.append({
                "page_number": page_num + 1,
                "base64": b64,
                "media_type": "image/png",
            })

        doc.close()
        logger.info("Rendered %d pages from %s", len(pages), file_path)
        return pages

    def image_to_payload(self, file_path: str) -> dict:
        """Encode a standalone image file for vision input."""
        ext = Path(file_path).suffix.lower()
        media_type = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"

        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        return {
            "page_number": 1,
            "base64": b64,
            "media_type": media_type,
        }

    def process(self, file_path: str) -> list[dict]:
        """
        Entry point — returns a list of page image payloads
        regardless of whether the input was a PDF or a single image.
        """
        file_type = self.detect_file_type(file_path)

        if file_type == "pdf":
            return self.pdf_to_page_images(file_path)
        else:
            return [self.image_to_payload(file_path)]

    def batch_pages(self, pages: list[dict]) -> list[list[dict]]:
        """
        Split a long document into batches of MAX_PAGES_PER_BATCH.
        Used when a document is too large to send in a single vision call.
        """
        return [
            pages[i:i + MAX_PAGES_PER_BATCH]
            for i in range(0, len(pages), MAX_PAGES_PER_BATCH)
        ]


document_processor = DocumentProcessor()