# PDFPreview

This cog allows you to preview PDF files in Discord.

When a PDF is attached to (or linked in) a message, the bot renders the first
few pages to images and posts them in a single gallery embed, along with the
total page count, file size, and a VirusTotal scan result.

## Commands

- `/pdf toggle` — enable or disable PDF previews for the server.
- `/pdf pages <1-4>` — set how many pages are included in each preview
  (server-configurable, defaults to 1). Discord renders at most 4 images in a
  gallery embed, so previews are capped at 4 pages.
