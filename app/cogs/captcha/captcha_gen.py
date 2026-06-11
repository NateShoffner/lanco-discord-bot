from io import BytesIO

from captcha.image import ImageCaptcha
from PIL import Image as PilImage

from .models import CaptchaChallenge, CaptchaMode

_FONT_SIZES = [40, 44, 48]


def generate_captcha(mode: CaptchaMode) -> CaptchaChallenge:
    answer = mode.generate_answer()
    parts = answer.split()

    if len(parts) > 1:
        # multi-word: render each word separately and stack vertically
        part_images = [_render_part(p) for p in parts]
        gap = 8
        total_h = sum(img.height for img in part_images) + gap * (len(part_images) - 1)
        max_w = max(img.width for img in part_images)
        combined = PilImage.new("RGB", (max_w, total_h), (255, 255, 255))
        y = 0
        for img in part_images:
            combined.paste(img, ((max_w - img.width) // 2, y))
            y += img.height + gap
        buf = BytesIO()
        combined.save(buf, format="PNG")
    else:
        img = _render_part(answer)
        buf = BytesIO()
        img.save(buf, format="PNG")

    return CaptchaChallenge(answer=answer, image_bytes=buf.getvalue())


def _render_part(text: str) -> PilImage.Image:
    width = max(160, len(text) * 32)
    generator = ImageCaptcha(width=width, height=80, font_sizes=_FONT_SIZES)
    buf = BytesIO()
    generator.write(text, buf, format="PNG")
    buf.seek(0)
    return PilImage.open(buf).copy()
