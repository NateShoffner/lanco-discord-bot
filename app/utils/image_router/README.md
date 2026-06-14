# Image Processor Router

Core bot functionality (not a cog) that owns the **single** image-bearing
`on_message` handler for the whole bot. Image cogs register an `ImageIntent`
instead of hooking `on_message` themselves, so they never re-download the same
attachment or independently call a vision model. The router gates cheaply,
downloads once, runs one shared vision call, scores, arbitrates, and dispatches.

The router is constructed in `LancoBot.__init__` and registers its listener in
`setup_hook`. Cogs interact with it only by registering intents.

## Flow per image

1. **Extract** candidate image(s) from the message (attachments, else embeds).
   Only the first image is routed unless `process_all_images` is set.
2. **Cheap gate**: each intent's `cheap_predicate(candidate, message)` runs
   (sync, metadata only: extension / mime / size / source). No download, no AI.
   If none qualify, the router stops here.
3. **Download once**: the image is fetched a single time; the bytes are shared
   with every qualifying intent.
4. **Shared vision pass**: the `questions` from all qualifying intents are
   unioned (de-duped by key) and asked in **one** model call. Skipped entirely
   if no qualifying intent declared questions.
5. **Score**: each intent's `confidence(ctx)` returns 0.0–1.0, reading the
   shared answers (`ctx.answer("key")`) plus its own cheap conditions.
6. **Arbitrate**: sub-threshold scores are dropped; each `conflict_group`
   collapses to its highest score; the overall top-confidence intent always
   runs; additional intents run only if `exclusive=False`.
7. **Dispatch**: selected intents' `process(ctx)` run. The downloaded file is
   cleaned up afterwards.

## The `ImageIntent` contract

| Field | Type | Meaning |
|-------|------|---------|
| `cheap_predicate` | `(ImageCandidate, Message) -> bool` | Sync metadata-only gate. No I/O, no AI. |
| `confidence` | `async (ImageContext) -> float` | 0.0–1.0. Reads `ctx.answers` + own cheap checks. |
| `process` | `async (ImageContext) -> None` | The work; runs only if selected. |
| `questions` | `list[VisionQuestion]` | Contributed to the single shared vision call. Optional. |
| `conflict_group` | `str \| None` | Intents sharing a group compete; the highest score wins. |
| `exclusive` | `bool` (default `True`) | **Isolated by default**: runs only as the top winner. Set `False` to coexist with other winners. |
| `threshold` | `float` (default `0.5`) | Minimum confidence to be eligible. |

### `VisionQuestion`

```python
VisionQuestion(key="is_cat", prompt="Is the main subject a cat?", kind="bool")
```

- `key`: the field name read back via `ctx.answer(key)`.
- `prompt`: natural-language question handed to the model.
- `kind`: `"bool"` (default), `"int"`, `"str"`, or `"float"`.

Questions from different intents are unioned and de-duped by `key`, so two cogs
asking the same thing cost only one field in the shared call.

### `ImageContext`

Passed to `confidence` and `process`:

- `ctx.message`: the originating `discord.Message`.
- `ctx.candidate`: the `ImageCandidate` (`url`, `content_type`, `size`,
  `filename`, `data`, `extension`).
- `ctx.answers`: the shared vision result dict.
- `ctx.answer(key, default=None)`: convenience accessor.

## Implementing an image processor cog

Subclass `ImageProcessorCog` (which is a `LancoCog`) and register intents in
`cog_load`. The cog never touches `on_message` or downloads anything.

```python
from discord.ext import commands
from utils.image_router import ImageContext, ImageProcessorCog, VisionQuestion


class CatDog(ImageProcessorCog, name="CatDog", description="Reacts to pets"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()

        # Cat and dog share a conflict_group: a photo is one or the other, so
        # only the higher-confidence intent fires, never both.
        self.register_image_intent(
            name="nice_cat",
            cheap_predicate=self.is_image,          # provided by ImageProcessorCog
            questions=[VisionQuestion("is_cat", "Is the main subject a cat?")],
            confidence=self.cat_confidence,
            process=self.say_nice_cat,
            conflict_group="catdog",
        )
        self.register_image_intent(
            name="nice_dog",
            cheap_predicate=self.is_image,
            questions=[VisionQuestion("is_dog", "Is the main subject a dog?")],
            confidence=self.dog_confidence,
            process=self.say_nice_dog,
            conflict_group="catdog",
        )

    async def cat_confidence(self, ctx: ImageContext) -> float:
        return 0.95 if ctx.answer("is_cat") else 0.0

    async def dog_confidence(self, ctx: ImageContext) -> float:
        return 0.95 if ctx.answer("is_dog") else 0.0

    async def say_nice_cat(self, ctx: ImageContext) -> None:
        await ctx.message.reply("nice cat")

    async def say_nice_dog(self, ctx: ImageContext) -> None:
        await ctx.message.reply("nice dog")


async def setup(bot):
    await bot.add_cog(CatDog(bot))
```

Because both intents declare their vision questions, a single posted image
triggers **one** vision call answering both `is_cat` and `is_dog`; the router
then dispatches only the winner.

### Notes

- `is_image` is a default cheap predicate on `ImageProcessorCog` that accepts
  anything with an `image/*` content type or a known image extension. Supply
  your own for narrower gating (e.g. only `.png`).
- Intents are removed automatically when the cog unloads (`LancoCog.cog_unload`),
  so hot-reload leaves no stale intents.
- If `confidence` needs non-image data (the poster's timezone, a guild config,
  the current time), read it directly inside `confidence`; only the expensive
  image classification belongs in the shared `questions`.
- To react to an image **regardless** of what else matches, set `exclusive=False`
  so the intent can run alongside another group's winner. By default it will not.

## Configuration

- `IMAGE_ROUTER_ALL_IMAGES=true`: route every image in a message instead of
  only the first. Defaults to first-image-only, matching the other image cogs.
