import asyncio
import websockets
import json

async def test_raw():
    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            command = {"action": "getScore", "params": {}}
            await websocket.send(json.dumps(command))
            response_str = await websocket.recv()
            response = json.loads(response_str)
            if response.get("status") == "success":
                analysis = response.get("result", {}).get("analysis", {})
                if not analysis:
                    analysis = response.get("analysis", {})
                
                # Check first few measures for lyrics
                found_lyrics = False
                for measure in analysis.get("measures", [])[:10]:
                    for staff, elements in measure.get("elements", {}).items():
                        for el in elements:
                            if "lyrics" in el and el["lyrics"]:
                                print(f"Found lyrics! {el['lyrics']}")
                                found_lyrics = True
                
                if not found_lyrics:
                    print("No lyrics found in the raw JSON for the first 10 measures.")
            else:
                print("Error:", response)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_raw())
