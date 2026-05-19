import discord
import asyncio
import logging
import json
import re

import components_v2
import dumper
import utils

file = open("token.txt").read().strip().split()
token = file[0]
channel = file[1]

logging.getLogger("discord").setLevel(logging.CRITICAL)
logging.getLogger("discord.client").setLevel(logging.CRITICAL)
logging.getLogger("discord.state").setLevel(logging.CRITICAL)

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(enable_debug_events=True)

        self.matches = []
        self.captcha = False
        self.sending = False
        self.index = 0

        self.dm = None
        self.owo_msg = None

    async def on_ready(self):
        print(f'Logged in as {self.user}')

        self.local_headers = await components_v2.headers.generate_headers()
        self.local_headers["Authorization"] = token

    async def next_page(self, channel):
        for btn in self.owo_btn:
            if btn.emoji.name == "forward":
                if not btn.disabled:
                    await asyncio.sleep(0.25)
                    await btn.click(self.ws.session_id, self.local_headers, channel.guild.id)

    async def on_socket_raw_receive(self, msg):
        parsed_msg = json.loads(msg)
        if parsed_msg["t"] not in ("MESSAGE_UPDATE", "MESSAGE_CREATE"):
            return
        message = components_v2.message.get_message_obj(parsed_msg["d"])

        if message.channel_id != channel:
            return
        chan = self.get_channel(channel)

        if message.author.id == utils.id_owo:
            if message.buttons:
                for btn in message.buttons:
                    if btn.emoji.name in ("back", "forward"):
                        self.owo_msg = message
                        self.owo_btn = btn

        if message.author.id == utils.id_neonutil:
            _msg = await chan.fetch_message(message.id)

            if self.captcha or not _msg or not _msg.embeds or not _msg.components:
                return
            if not self.owo_msg or not self.owo_btn:
                return

            for comps in _msg.components:
                for i in comps.children:
                    if not i.emoji.name in ("❔", "📊", "🔃"):
                        return

            for embed in _msg.embeds:
                if embed.author.name and "Max qualities for" in embed.author.name:
                    if embed.description:
                        self.matches = re.findall(r'`(.+)`.+max_possible', embed.description)

                        if self.matches:
                            print(f"Captured IDs: {self.matches} in {self.owo_btn[2].label}")

                            if not self.sending:
                                self.sending = True
                                asyncio.create_task(self.worker(chan))
                        else:
                            await self.next_page(chan)

    # maybe "worker" isnt needed, put in the for loop at if messages == neonutil
    # or maybe it is, because imagine all this in the for loop
    # "but this is what self.sending is for" well idk (im going insane)
    async def worker(self, chan):
        for i in self.matches:
            if self.captcha:
                await asyncio.sleep(1)
                continue

            print(f"sent: owow {i}")
            await chan.send(f"ww {i}")
            await asyncio.sleep(5.1)

            self.index += 1

        self.matches.clear()
        self.index = 0
        self.sending = False

        await self.next_page(chan)

    async def on_message(self, message):
        if not message.author.id == utils.id_owo:
            return

        if not self.owo_dm:
            self.owo_dm = await message.author.create_dm()
            return

        if "⚠️" in message.content and message.channel.id == channel:
            self.captcha = True
            if self.index > 0:
                self.index -= 1
            utils.log("Captcha Detected! ⚠️", "red")
            utils.notify(f"Captcha Detected!", f"Captcha - {self.user.name}!")

        if "👍" in message.content and message.channel.id == self.owo_dm:
            self.captcha = False
            utils.log("Captcha Solved ✅", "green")

client = MyClient()
client.run(token)