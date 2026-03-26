"""
Comic Assembler — builds pages from generated panels.
Handles proper speech bubbles, layout, and export.
"""

import asyncio
import io
import logging
import textwrap
import zipfile
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

PAGE_SIZES = {
    "manga":   (1654, 2339),    # A5 at 200dpi
    "manhwa":  (860, 2400),     # Webtoon strip section
    "western": (1988, 3056),    # US comic at 200dpi
}

PANELS_PER_ROW = {
    "manga":   3,
    "manhwa":  1,     # Always single column for webtoon
    "western": 3,
}

MARGIN = 24
GAP = 8

# Font paths to try in order
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    """Wrap text to fit within max_width pixels."""
    if not text:
        return []
    words = text.split()
    lines = []
    current = ""
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)

    for word in words:
        test = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_speech_bubble(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    bubble_style: str = "speech",
    font_size: int = 18,
) -> int:
    """Draw a speech bubble. Returns the height used."""
    if not text.strip():
        return 0

    font = _load_font(font_size)
    pad = 10
    bubble_w = min(max_width - 20, 280)
    lines = _wrap_text(text, font, bubble_w - pad * 2)

    dummy = Image.new("RGB", (1, 1))
    d = ImageDraw.Draw(dummy)
    line_h = max(d.textbbox((0, 0), "Ay", font=font)[3] + 4, 20)
    text_h = line_h * len(lines)
    total_h = text_h + pad * 2

    # Bubble background
    bg_color = {
        "thought":   "#e8f4fd",
        "shout":     "#fff9c4",
        "whisper":   "#f0f0f0",
        "narration": "#fffde7",
    }.get(bubble_style, "white")

    border_color = {
        "shout":   "#e53935",
        "whisper": "#9e9e9e",
    }.get(bubble_style, "#1a1a1a")

    # Draw rounded rectangle
    r = 12
    draw.rounded_rectangle(
        [x, y, x + bubble_w, y + total_h],
        radius=r,
        fill=bg_color,
        outline=border_color,
        width=2,
    )

    # Draw text lines
    text_color = "#1a1a1a"
    for i, line in enumerate(lines):
        draw.text((x + pad, y + pad + i * line_h), line, fill=text_color, font=font)

    return total_h + 6  # 6px gap below bubble


class ComicAssembler:
    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.comics_path = self.storage_path / "comics"
        self.comics_path.mkdir(parents=True, exist_ok=True)

    async def _fetch_image(self, url: str) -> Image.Image | None:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception as e:
            log.warning(f"Failed to fetch image {url[:60]}: {e}")
            return None

    def _panel_placeholder(self, w: int, h: int, text: str = "") -> Image.Image:
        img = Image.new("RGB", (w, h), "#2a2a3a")
        draw = ImageDraw.Draw(img)
        font = _load_font(14)
        if text:
            lines = textwrap.wrap(text, width=30)
            y = h // 2 - len(lines) * 10
            for line in lines:
                draw.text((w // 2, y), line, fill="#666688", font=font, anchor="mm")
                y += 22
        return img

    def _calculate_layout(
        self, layout: str, style: str, page_w: int, page_h: int, panel_count: int
    ) -> list[tuple[int, int, int, int]]:
        """Return list of (x, y, w, h) for each panel slot."""
        uw = page_w - 2 * MARGIN
        uh = page_h - 2 * MARGIN

        if layout == "splash" or panel_count == 1:
            return [(MARGIN, MARGIN, uw, uh)]

        # Manhwa: always single column
        if style == "manhwa":
            ph = (uh - GAP * (panel_count - 1)) // panel_count
            return [(MARGIN, MARGIN + i * (ph + GAP), uw, ph) for i in range(panel_count)]

        cols = min(PANELS_PER_ROW.get(style, 3), panel_count)
        rows = (panel_count + cols - 1) // cols
        pw = (uw - GAP * (cols - 1)) // cols
        ph = (uh - GAP * (rows - 1)) // rows

        positions = []
        for i in range(panel_count):
            col = i % cols
            row = i // cols
            positions.append((MARGIN + col * (pw + GAP), MARGIN + row * (ph + GAP), pw, ph))
        return positions

    async def assemble_page(
        self,
        page_data: dict,
        style: str,
        add_text: bool = True,
    ) -> Image.Image:
        page_w, page_h = PAGE_SIZES.get(style, PAGE_SIZES["manhwa"])
        panels = page_data.get("panels", [])
        layout = page_data.get("layout", "grid_2x3")

        page = Image.new("RGB", (page_w, page_h), "white")

        if not panels:
            return page

        positions = self._calculate_layout(layout, style, page_w, page_h, len(panels))

        for panel, (px, py, pw, ph) in zip(panels, positions):
            image_data = panel.get("image") or {}
            url = image_data.get("url") if image_data else None

            if url:
                img = await self._fetch_image(url)
                if img is None:
                    img = self._panel_placeholder(pw, ph, panel.get("scene_description", ""))
                else:
                    img = img.resize((pw, ph), Image.LANCZOS)
            else:
                img = self._panel_placeholder(pw, ph, panel.get("scene_description", ""))

            page.paste(img, (px, py))

            # Panel border
            draw = ImageDraw.Draw(page)
            draw.rectangle([px, py, px + pw - 1, py + ph - 1], outline="#0d0d0d", width=3)

            # Speech bubbles — stacked in top-left corner of panel
            if add_text:
                dialogue = panel.get("dialogue", [])
                bub_x = px + 10
                bub_y = py + 10
                bub_max_w = pw - 20
                for line in dialogue[:3]:   # max 3 bubbles per panel
                    text = line.get("text", "").strip()
                    if not text:
                        continue
                    speaker = line.get("speaker", "")
                    display = f"{speaker}: {text}" if speaker else text
                    used_h = _draw_speech_bubble(
                        draw, display, bub_x, bub_y, bub_max_w,
                        bubble_style=line.get("bubble_style", "speech"),
                        font_size=max(14, min(20, pw // 20)),
                    )
                    bub_y += used_h
                    if bub_y > py + ph - 40:
                        break   # No room for more bubbles

                # SFX in bottom-right
                sfx_list = panel.get("sfx", [])
                if sfx_list:
                    sfx_font = _load_font(max(20, pw // 10))
                    draw.text(
                        (px + pw - 10, py + ph - 10),
                        sfx_list[0].upper(),
                        fill="#cc0000",
                        font=sfx_font,
                        anchor="rb",
                    )

        return page

    async def export_cbz(self, comic_id: str, pages: list[Image.Image]) -> str:
        path = self.comics_path / f"{comic_id}.cbz"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(pages):
                buf = io.BytesIO()
                page.save(buf, format="PNG", optimize=True)
                zf.writestr(f"page_{i+1:03d}.png", buf.getvalue())
        log.info(f"Exported CBZ: {path}")
        return str(path)

    async def export_webp_strip(self, comic_id: str, pages: list[Image.Image]) -> str:
        if not pages:
            return ""
        strip = Image.new("RGB", (pages[0].width, sum(p.height for p in pages)), "white")
        y = 0
        for page in pages:
            strip.paste(page, (0, y))
            y += page.height
        path = self.comics_path / f"{comic_id}_strip.webp"
        strip.save(path, format="WEBP", quality=88, method=4)
        log.info(f"Exported webtoon strip: {path}")
        return str(path)
