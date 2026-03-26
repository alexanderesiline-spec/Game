"""
Comic Assembler — takes generated panels and assembles them into pages.

Handles:
- Speech bubble overlay (text positioning)
- SFX text styling
- Page layout composition
- Export to PDF / CBZ / PNG strip (for webtoon)
"""

import asyncio
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont


# Bubble styles
BUBBLE_STYLES = {
    "speech": {"shape": "ellipse", "tail": True, "bg": "white", "border": "black"},
    "thought": {"shape": "cloud", "tail": True, "bg": "white", "border": "black"},
    "shout": {"shape": "spiky", "tail": True, "bg": "white", "border": "black"},
    "whisper": {"shape": "dashed_ellipse", "tail": False, "bg": "white", "border": "gray"},
    "narration": {"shape": "rect", "tail": False, "bg": "#fffee0", "border": "#888"},
}

PAGE_SIZES = {
    "manga": (2480, 3508),    # A4 at 300dpi
    "manhwa": (1080, 3000),   # Webtoon strip
    "western": (2550, 3300),  # US comic standard
}


class ComicAssembler:
    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.comics_path = self.storage_path / "comics"
        self.comics_path.mkdir(parents=True, exist_ok=True)

    async def download_image(self, url: str) -> Image.Image:
        """Download an image from a URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGBA")

    def add_speech_bubble(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple[int, int],
        bubble_style: str = "speech",
        font_size: int = 24,
    ) -> None:
        """Draw a speech bubble with text on an image."""
        style = BUBBLE_STYLES.get(bubble_style, BUBBLE_STYLES["speech"])
        x, y = position

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

        # Measure text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        padding = 16

        bubble_x1 = x
        bubble_y1 = y
        bubble_x2 = x + text_w + padding * 2
        bubble_y2 = y + text_h + padding * 2

        # Draw bubble background
        draw.ellipse(
            [bubble_x1, bubble_y1, bubble_x2, bubble_y2],
            fill=style["bg"],
            outline=style["border"],
            width=3,
        )
        # Draw text
        draw.text(
            (bubble_x1 + padding, bubble_y1 + padding),
            text,
            fill="black",
            font=font,
        )

    async def assemble_page(
        self,
        page_data: dict,
        style: str,
        add_text: bool = True,
    ) -> Image.Image:
        """Assemble a single page from its panels."""
        page_w, page_h = PAGE_SIZES.get(style, PAGE_SIZES["manhwa"])
        page_img = Image.new("RGB", (page_w, page_h), "white")

        panels = page_data.get("panels", [])
        if not panels:
            return page_img

        layout = page_data.get("layout", "grid_2x3")

        # Calculate panel positions based on layout
        positions = self._calculate_layout(layout, page_w, page_h, len(panels))

        for i, (panel, pos) in enumerate(zip(panels, positions)):
            image_data = panel.get("image", {})
            image_url = image_data.get("url") if image_data else None

            if not image_url:
                # Placeholder if generation failed
                placeholder = Image.new("RGB", (pos[2], pos[3]), "#e0e0e0")
                draw = ImageDraw.Draw(placeholder)
                draw.text((pos[2] // 2 - 30, pos[3] // 2), "Panel", fill="#999")
                panel_img = placeholder
            else:
                try:
                    panel_img = await self.download_image(image_url)
                    panel_img = panel_img.convert("RGB").resize((pos[2], pos[3]), Image.LANCZOS)
                except Exception:
                    panel_img = Image.new("RGB", (pos[2], pos[3]), "#f0f0f0")

            page_img.paste(panel_img, (pos[0], pos[1]))

            # Add dialogue text overlays
            if add_text:
                draw = ImageDraw.Draw(page_img)
                dialogue = panel.get("dialogue", [])
                for j, line in enumerate(dialogue[:3]):  # max 3 bubbles per panel
                    bubble_x = pos[0] + 20
                    bubble_y = pos[1] + 20 + (j * 80)
                    self.add_speech_bubble(
                        draw,
                        line.get("text", "")[:80],  # truncate long lines
                        (bubble_x, bubble_y),
                        bubble_style=line.get("bubble_style", "speech"),
                    )

                # Add SFX
                sfx_list = panel.get("sfx", [])
                if sfx_list:
                    draw.text(
                        (pos[0] + pos[2] // 2, pos[1] + pos[3] - 40),
                        sfx_list[0],
                        fill="red",
                        anchor="mm",
                    )

        # Draw panel borders
        draw = ImageDraw.Draw(page_img)
        for pos in positions:
            draw.rectangle(
                [pos[0], pos[1], pos[0] + pos[2], pos[1] + pos[3]],
                outline="black",
                width=3,
            )

        return page_img

    def _calculate_layout(
        self, layout: str, page_w: int, page_h: int, panel_count: int
    ) -> list[tuple[int, int, int, int]]:
        """Return list of (x, y, width, height) for each panel."""
        margin = 20
        gap = 8
        usable_w = page_w - 2 * margin
        usable_h = page_h - 2 * margin

        if layout == "splash" or panel_count == 1:
            return [(margin, margin, usable_w, usable_h)]

        if layout == "vertical_strip" or panel_count <= 3:
            panel_h = (usable_h - gap * (panel_count - 1)) // panel_count
            return [
                (margin, margin + i * (panel_h + gap), usable_w, panel_h)
                for i in range(panel_count)
            ]

        # Default: auto grid
        cols = 2 if panel_count <= 4 else 3
        rows = (panel_count + cols - 1) // cols
        panel_w = (usable_w - gap * (cols - 1)) // cols
        panel_h = (usable_h - gap * (rows - 1)) // rows

        positions = []
        for i in range(panel_count):
            col = i % cols
            row = i // cols
            x = margin + col * (panel_w + gap)
            y = margin + row * (panel_h + gap)
            positions.append((x, y, panel_w, panel_h))
        return positions

    async def export_cbz(self, comic_id: str, pages: list[Image.Image]) -> str:
        """Export assembled pages as a CBZ (comic book zip) file."""
        cbz_path = self.comics_path / f"{comic_id}.cbz"
        with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(pages):
                buf = io.BytesIO()
                page.save(buf, format="PNG")
                zf.writestr(f"page_{i+1:03d}.png", buf.getvalue())
        return str(cbz_path)

    async def export_pdf(self, comic_id: str, pages: list[Image.Image]) -> str:
        """Export assembled pages as a PDF."""
        pdf_path = self.comics_path / f"{comic_id}.pdf"
        if pages:
            pages[0].save(
                pdf_path,
                save_all=True,
                append_images=pages[1:],
                format="PDF",
            )
        return str(pdf_path)

    async def export_webp_strip(self, comic_id: str, pages: list[Image.Image]) -> str:
        """Export as a long vertical strip (webtoon format)."""
        if not pages:
            return ""
        total_h = sum(p.height for p in pages)
        strip = Image.new("RGB", (pages[0].width, total_h), "white")
        y_offset = 0
        for page in pages:
            strip.paste(page, (0, y_offset))
            y_offset += page.height
        strip_path = self.comics_path / f"{comic_id}_strip.webp"
        strip.save(strip_path, format="WEBP", quality=85)
        return str(strip_path)
