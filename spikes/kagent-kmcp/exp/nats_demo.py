import asyncio, json
import nats

async def main():
    nc = await nats.connect("nats://127.0.0.1:14222")
    got = asyncio.Event()

    async def on_pet_sold(msg):
        print("handover got", msg.subject, json.loads(msg.data))
        got.set()

    await nc.subscribe("petstore.sales.pet-sold", cb=on_pet_sold)
    await nc.publish("petstore.sales.pet-sold", json.dumps({"pet_id": "rex", "slot": "Sat 14:00"}).encode())
    await asyncio.wait_for(got.wait(), 2)
    await nc.drain()

asyncio.run(main())
