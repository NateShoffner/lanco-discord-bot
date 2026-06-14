# Router

Core bot functionality (not a cog) that owns the **single** `on_message` handler
for the whole bot. Cogs register an `Intent` instead of hooking `on_message`
themselves, so they never re-download the same attachment or independently call a
vision model.

## Three layers

The routers form an inheritance chain, each adding one capability:

```
MessageRouter            registry, cheap gate, score, arbitrate, dispatch
  -> FileRouter          extract attachments, download each once
       -> ImageRouter    filter to images, one shared vision call
```

Only `ImageRouter` is instantiated (in `LancoBot.__init__`); it inherits message-
and file-level handling. There is one registry (`bot.processors`) and one
listener. Each intent declares a **level** (`message`, `file`, or `image`); the
router evaluates it against candidates at or below that level. Because an
`ImageCandidate` is a `FileCandidate`, one downloaded image serves both file and
image intents.

## Flow per candidate

1. **Extract** candidates from the message. Message level yields one candidate
   wrapping the message; file/image levels yield one per attachment (images
   become `ImageCandidate`, everything else `FileCandidate`).
2. **Gate**: each applicable intent's `cheap_predicate(candidate, message)`
   runs (sync, metadata only, no I/O). This is the cog's own arbiter of whether
   it wants the message; it runs before any download or model call.
3. **Prepare**: file/image candidates are downloaded once; bytes shared.
4. **Enrich**: for image candidates, the `questions` from all qualifying image
   intents are unioned (de-duped by key) and asked in **one** vision call.
5. **Score**: each intent's `confidence(ctx)` returns 0.0 to 1.0.
6. **Arbitrate**: sub-threshold scores dropped; each `conflict_group` collapses
   to its highest score; the top-confidence intent always runs; others run only
   if `exclusive=False`.
7. **Dispatch**: selected intents' `process(ctx)` run; downloads cleaned up.

## Intent fields

| Field | Meaning |
|-------|---------|
| `cheap_predicate(candidate, message) -> bool` | The cog's arbiter: sync, metadata only, no I/O. Decides whether this intent wants the message; runs before any download or model call. |
| `confidence(ctx) -> float` | 0.0 to 1.0. Reads `ctx` plus own cheap checks. |
| `process(ctx) -> None` | The work; runs only if selected. |
| `questions` (image only) | `list[VisionQuestion]` for the shared vision call. |
| `conflict_group` | Intents sharing a group compete; the highest score wins. |
| `exclusive` (default `True`) | Isolated by default: runs only as the top winner. Set `False` to coexist. |
| `threshold` (default `0.5`) | Minimum confidence to be eligible. |

## The cog decides whether to run

There is no router-side channel/role/pattern config. Like a URL-handler cog
deciding in its own listener, each intent's `cheap_predicate` is the sole arbiter
of whether the router runs it for a given message. The cog puts whatever logic it
wants there: channel, role, user, regex on `message.content`, content type, NSFW
flag, and so on. Because it runs before download and vision, declining there
costs nothing.

```python
def should_handle(self, candidate, message):
    return (
        message.channel.id in self.pets_channels      # cog owns its own config
        and self.is_image(candidate, message)         # helper for the common case
    )

self.register_image_intent(
    name="nice_cat",
    cheap_predicate=self.should_handle,
    questions=[VisionQuestion("is_cat", "Is the main subject a cat?")],
    confidence=self.cat_confidence,
    process=self.say_nice_cat,
)
```

`is_image` is a convenience predicate on `ProcessorCog` for the common "any
image" case; compose it with your own checks as above, or write a predicate from
scratch.

`ctx` is a `RouterContext` (`message`, `candidate`); `FileContext` adds the
downloaded candidate; `ImageContext` adds `answers` and `ctx.answer(key)`.

## Implementing a processor cog

Subclass `ProcessorCog` (a `LancoCog`) and register intents in `cog_load`. The
cog never touches `on_message` or downloads anything.

```python
from discord.ext import commands
from utils.router import ImageContext, ProcessorCog, VisionQuestion


class CatDog(ProcessorCog, name="CatDog", description="Reacts to pets"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        # Cat and dog share a conflict_group: a photo is one or the other, so
        # only the higher-confidence intent fires, never both.
        self.register_image_intent(
            name="nice_cat",
            cheap_predicate=self.is_image,          # provided by ProcessorCog
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

`register_message_intent` and `register_file_intent` exist for the other levels;
they take the same arguments minus `questions`.

### Notes

- `is_image` is a default image cheap predicate on `ProcessorCog`. Supply your
  own for narrower gating (e.g. only `.png`).
- Intents are removed automatically on cog unload, so hot-reload leaves none
  stale.
- Read non-image data (timezone, config, current time) directly inside
  `confidence`; only the expensive image classification belongs in `questions`.
- Set `exclusive=False` to react alongside another group's winner. By default it
  will not.

## Configuration

- `IMAGE_ROUTER_ALL_IMAGES=true`: route every image in a message instead of only
  the first. Defaults to first-image-only.
