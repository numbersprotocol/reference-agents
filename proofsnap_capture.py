"""ProofSnap-style screenshot capture and watermark helpers."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from playwright.sync_api import TimeoutError as PlaywrightTimeout

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "Word-Logo-Bright-crop.png"


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu") / font_name,
        Path("/usr/share/fonts/dejavu") / font_name,
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _draw_rounded_shadow(
    image: Image.Image,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
) -> None:
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shifted = (xy[0], xy[1] + 2, xy[2], xy[3] + 2)
    shadow_draw.rounded_rectangle(shifted, radius=radius, fill=(0, 0, 0, 26))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    image.alpha_composite(shadow)

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=(255, 255, 255, 102), width=1)
    image.alpha_composite(overlay)


def _format_proofsnap_timestamp(timestamp: datetime) -> tuple[str, str]:
    local = timestamp.astimezone()
    return local.strftime("%H:%M"), local.strftime("%d/%m/%Y %a")


def apply_proofsnap_watermark(image_path: str | Path, timestamp: datetime) -> None:
    """Apply the ProofSnap extension default timestamp and logo watermark in-place."""
    path = Path(image_path)
    image = Image.open(path).convert("RGBA")
    width, height = image.size

    time_text, date_text = _format_proofsnap_timestamp(timestamp)

    base_font_size = max(20, height // 35)
    time_font_size = int(base_font_size * 2)
    date_font_size = int(base_font_size)
    time_font = _load_font(time_font_size, bold=True)
    date_font = _load_font(date_font_size)

    measure = ImageDraw.Draw(image)
    time_width, time_height = _text_size(measure, time_text, time_font)
    date_width, date_height = _text_size(measure, date_text, date_font)

    padding = 16
    box_width = max(time_width, date_width) + padding * 2
    box_height = time_height + date_height + padding * 2 + 12
    margin = 20
    pos_x = margin
    pos_y = 60

    _draw_rounded_shadow(
        image,
        (pos_x, pos_y, pos_x + box_width, pos_y + box_height),
        radius=8,
        fill=(255, 255, 255, 153),
    )

    draw = ImageDraw.Draw(image)
    draw.text((pos_x + padding, pos_y + padding), time_text, font=time_font, fill=(26, 26, 26, 255))
    draw.text(
        (pos_x + padding, pos_y + padding + time_height + 8),
        date_text,
        font=date_font,
        fill=(26, 26, 26, 230),
    )

    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_width = max(100, width // 12)
        logo_height = int(logo_width * (157 / 828))
        logo = logo.resize((logo_width, logo_height), Image.LANCZOS)
        alpha = logo.getchannel("A").point(lambda value: int(value * 0.7))
        logo.putalpha(alpha)
        image.alpha_composite(logo, (width - logo_width - 20, height - logo_height - 20))

    image.convert("RGB").save(path, format="PNG")


def capture_page_screenshot(
    browser,
    url: str,
    tmp_path: str | Path,
    *,
    timestamp: datetime,
    timeout_ms: int,
    width: int,
    height: int,
    user_agent: str,
    logger: logging.Logger,
) -> tuple[str, str] | None:
    """Capture a page screenshot, add ProofSnap watermark, and return (html_hash, text_excerpt)."""
    context = None
    page = None
    try:
        context = browser.new_context(
            viewport={"width": width, "height": height},
            user_agent=user_agent,
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        html = page.content()
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

        try:
            raw_text = page.inner_text("body")
            excerpt = " ".join(raw_text.split())[:500]
        except Exception:
            excerpt = ""

        page.screenshot(path=str(tmp_path), full_page=False)
        apply_proofsnap_watermark(tmp_path, timestamp)
        logger.debug("screenshot ok with ProofSnap watermark hash=%s url=%s", content_hash[:12], url[:70])
        return content_hash, excerpt
    except PlaywrightTimeout:
        logger.warning("screenshot timeout (%sms) url=%s", timeout_ms, url[:80])
        return None
    except Exception as exc:
        logger.warning("screenshot failed url=%s err=%s", url[:80], exc)
        return None
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass
        if context:
            try:
                context.close()
            except Exception:
                pass
