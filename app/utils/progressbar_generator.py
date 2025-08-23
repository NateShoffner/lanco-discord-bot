from enum import Enum
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, field_validator


class SegmentKind(str, Enum):
    START = "start"
    MID = "mid"
    END = "end"


class ProgressEmoteGenerator(BaseModel):
    """
    Generate Discord progress-bar emotes and map percentages -> emote sequences.
    """

    # Output and layout
    output_dir: Path = Field(default=Path("emotes"))
    size_px: int = Field(default=128, ge=24, le=256)
    padding_px: int = Field(default=0, ge=0)
    corner_radius: int = Field(default=48, ge=0)

    # Colors (RGBA tuples)
    fill_color: Tuple[int, int, int, int] = (46, 204, 113, 255)  # green
    empty_color: Tuple[int, int, int, int] = (220, 223, 230, 255)  # gray
    bg_color: Tuple[int, int, int, int] = (0, 0, 0, 0)  # transparent

    # Border
    border_color: Tuple[int, int, int, int] = (33, 45, 62, 255)
    border_width: int = 0

    # Names
    emoji_names: Dict[str, str] = {
        "start_full": "pb_start_full",
        "start_empty": "pb_start_empty",
        "mid_full": "pb_mid_full",
        "mid_empty": "pb_mid_empty",
        "end_full": "pb_end_full",
        "end_empty": "pb_end_empty",
    }

    @field_validator("corner_radius")
    @classmethod
    def _cap_radius(cls, v, info):
        size_px = info.data.get("size_px", 128)
        pad = info.data.get("padding_px", 8)
        max_r = max(0, (size_px - 2 * pad) // 2)
        return min(v, max_r)

    # ----------------------- Public API -----------------------

    def generate_sprite_set(self) -> Dict[str, Path]:
        """
        Creates all 6 sprites and returns a dict of key -> filepath.
        """
        out = Path(self.output_dir)
        out.mkdir(parents=True, exist_ok=True)

        results: Dict[str, Path] = {}
        plan = [
            ("start_full", "start", True),
            ("start_empty", "start", False),
            ("mid_full", "mid", True),
            ("mid_empty", "mid", False),
            ("end_full", "end", True),
            ("end_empty", "end", False),
        ]

        for key, kind, filled in plan:
            img = self._draw_segment(kind=kind, filled=filled)
            basename = self.emoji_names[key]
            path = out / f"{basename}.png"
            img.save(path, format="PNG", optimize=True)
            results[key] = path

        return results

    def percentage_to_bar_parts(
        self,
        percent: float,
        segments: int = 10,
        emoji_markup: Dict[str, str] | None = None,
    ) -> list[str]:
        """
        Convert a percentage to a string of emote markup (or basenames).
        """
        segments = max(2, int(segments))
        p = max(0.0, min(100.0, float(percent)))
        filled = round((p / 100.0) * segments)

        parts: list[str] = []
        for idx in range(segments):
            if idx == 0:
                kind = SegmentKind.START
            elif idx == segments - 1:
                kind = SegmentKind.END
            else:
                kind = SegmentKind.MID

            is_full = idx < filled
            key = f"{kind.value}_{'full' if is_full else 'empty'}"
            name = emoji_markup.get(key) if emoji_markup else self.emoji_names[key]
            parts.append(name)

        return parts

    # ----------------------- Drawing -----------------------

    def _draw_segment(self, kind: SegmentKind, filled: bool) -> Image.Image:
        img = Image.new("RGBA", (self.size_px, self.size_px), self.bg_color)
        draw = ImageDraw.Draw(img)

        x0, y0 = self.padding_px, self.padding_px
        x1, y1 = self.size_px - self.padding_px, self.size_px - self.padding_px
        r = self.corner_radius

        fill = self.fill_color if filled else self.empty_color

        # shape differs slightly at start/end vs middle
        if kind == SegmentKind.MID:
            draw.rectangle(
                [x0, y0, x1, y1],
                fill=fill,
                outline=self.border_color,
                width=self.border_width,
            )
        elif kind == SegmentKind.START:
            draw.rounded_rectangle(
                [x0, y0, x1, y1],
                radius=r,
                fill=fill,
                outline=self.border_color,
                width=self.border_width,
            )
            # cover right side so only left is rounded
            draw.rectangle(
                [x0 + r, y0, x1, y1],
                fill=fill,
                outline=self.border_color,
                width=self.border_width,
            )
        elif kind == SegmentKind.END:
            draw.rounded_rectangle(
                [x0, y0, x1, y1],
                radius=r,
                fill=fill,
                outline=self.border_color,
                width=self.border_width,
            )
            # cover left side so only right is rounded
            draw.rectangle(
                [x0, y0, x1 - r, y1],
                fill=fill,
                outline=self.border_color,
                width=self.border_width,
            )

        return img
