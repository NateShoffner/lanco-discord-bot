Anime Today
===========

This cog will display an anime screenshot featuring the current date every morning in a specified channel.

🚀 Setup
----------------

Every morning the bot will post a screenshot in a specified channel if it's enabled. The screenshots are saved in the cog's data directory with the following format:

`<month_number>_<month_name>/<day_number>/Shots`

Then a random screenshot is seleected from that directory and posted to the specified channel.

Additioanlly, if a .txt file is present in the directory with the same filename as the screenshot, the bot will post the contents of the file as a message with the screenshot as the anime title.

Assets can be populated using [anime-today-scraper](https://github.com/NateShoffner/anime-today-scraper).p

