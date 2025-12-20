import asyncio
from loader import TxtLoader
from token_rotator import TokenRotator
from watcher import watch_channel

async def main():
    tokens = TxtLoader.loads("tokens.txt")
    channels = TxtLoader.loads("channels.txt")
    print(tokens)
    print(channels)
    if len(tokens) < len(channels):
        raise RuntimeError("Số token phải >= số channel")

    tasks = []

    for i, channel_id in enumerate(channels):
        print(f"{i} - {channel_id}")
        rotator = TokenRotator(tokens, start_index=i)
        tasks.append(
            asyncio.create_task(
                watch_channel(channel_id, rotator)
            )
        )

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
