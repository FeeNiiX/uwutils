import discord
import time

import components_v2
import dumper

token = open("token.txt").read().strip()
id_channel = 1389314043910819870
id_message = 1491910796471701504

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(enable_debug_events=True)

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(id_channel)
        msg = await channel.fetch_message(id_message)

        if not msg:
            return

        dumper.savey(msg, depth=6)
        time.sleep(1)
        await self.close()

    # async def on_socket_raw_receive(self, msg):
    #     parsed_msg = json.loads(msg)
    #     if parsed_msg["t"] not in ("MESSAGE_UPDATE", "MESSAGE_CREATE"):
    #         return

    #     # message = components_v2.message.get_message_obj(parsed_msg["d"])

    #     if self.printed <= 100:
    #         self.printed += 1
    #         print(self.printed)
    #         # dumper.printy(parsed_msg)
    #         dumper.savey(parsed_msg)
    #         if self.printed == 100:
    #             print("done")
    #             self.printed += 1

client = MyClient()
client.run(token)