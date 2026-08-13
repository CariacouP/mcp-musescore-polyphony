import asyncio
from src.client import MuseScoreClient
import json

async def main():
    client = MuseScoreClient()
    response = await client.send_command("getScore")
    with open("score_dump.json", "w") as f:
        json.dump(response, f, indent=2)
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
