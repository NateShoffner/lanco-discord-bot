import aiohttp


async def get_external_ip() -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.ipify.org") as resp:
            return await resp.text()
