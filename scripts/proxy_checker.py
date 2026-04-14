import asyncio
import sys
from pathlib import Path

import aiohttp

BASE_DIR = Path(__file__).resolve().parent.parent
PROXY_FILE = BASE_DIR / "config" / "proxy.txt"
PROXY_OUTPUT = BASE_DIR / "config" / "proxy.py"

TIMEOUT = 10
TEST_URL = "http://httpbin.org/ip"


async def check_proxy(session: aiohttp.ClientSession, proxy_url: str) -> bool:
    """Проверяет работоспособность прокси"""
    try:
        async with session.get(TEST_URL, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  FAIL {proxy_url}: {e}")
        return False


async def main():
    if not PROXY_FILE.exists():
        print(f"Proxy file not found: {PROXY_FILE}")
        sys.exit(1)

    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"Found {len(proxies)} proxies, checking...")

    working = []
    async with aiohttp.ClientSession() as session:
        tasks = [check_proxy(session, p) for p in proxies]
        results = await asyncio.gather(*tasks)

    for proxy, ok in zip(proxies, results):
        if ok:
            print(f"  OK   {proxy}")
            working.append(proxy)
        else:
            print(f"  FAIL {proxy}")

    # Сохраняем результат
    with open(PROXY_OUTPUT, "w", encoding="utf-8") as f:
        f.write("proxies = [\n")
        for p in working:
            f.write(f"    {repr(p)},\n")
        f.write("]\n")

    print(f"\nWorking: {len(working)}/{len(proxies)}")
    print(f"Saved to: {PROXY_OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
