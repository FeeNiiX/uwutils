import traceback
import discord
import asyncio
import json
import re

import components_v2
import dumper
import utils

token = open("token.txt").read().strip()

settings = utils.load("settings.json")
channel = settings["channel_misc"]

def lineno():
    frame_info = traceback.extract_stack()[-2]
    lineno = frame_info.lineno
    print(lineno)

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(enable_debug_events=True)

        self.matches = []
        self.captcha = False
        self.sending = False
        self.index = 0

        self.owo_dm = None
        self.owo_msg = None
        self.owo_next_btn = None
        self.label = None
        self.chan = None

    async def on_ready(self):
        print(f'Logged in as {self.user}')

        self.local_headers = await components_v2.headers.generate_headers()
        self.local_headers["Authorization"] = token

        self.chan = self.get_channel(channel)

    async def next_page(self, channel):
        if not self.owo_next_btn.disabled:
            print("Going to the next page!")
            await self.owo_next_btn.click(self.ws.session_id, self.local_headers, channel.guild.id)

    async def on_socket_raw_receive(self, msg):
        parsed_msg = json.loads(msg)
        if parsed_msg["t"] not in ("MESSAGE_UPDATE", "MESSAGE_CREATE"):
            return
        message = components_v2.message.get_message_obj(parsed_msg["d"])

        if not message.channel_id == channel or not self.chan:
            return

        if message.author.id == utils.id_owo:
            if message.buttons:
                for btn in message.buttons:
                    if btn.emoji and btn.emoji.name and btn.emoji.name == "forward":
                        self.owo_msg = await self.chan.fetch_message(message.id)
                        self.owo_next_btn = btn
                    if btn.custom_id == "noop":
                        self.label = btn.label

        if message.author.id == utils.id_neonutil:
            _msg = await self.chan.fetch_message(message.id)

            if self.captcha or not _msg or not _msg.embeds or not _msg.components:
                return
            if not self.owo_msg or not self.owo_next_btn or not self.label:
                return

            for comps in _msg.components:
                for child in comps.children:
                    if not child.emoji.name in ("❔", "📊", "🔃"):
                        return

            for embed in _msg.embeds:
                if embed.author.name and "Max qualities for" in embed.author.name:
                    if embed.description:
                        self.matches = re.findall(r'`(.+)`.+max_possible', embed.description)

                        if self.matches:
                            print(f"IDs in {self.label}: {self.matches}")

                            if not self.sending:
                                self.sending = True
                                asyncio.create_task(self.worker(self.chan))
                        else:
                            await self.next_page(self.chan)

    # maybe "worker" isnt needed, put in the for loop at if messages == neonutil
    # or maybe it is, because imagine all this in the for loop
    # "but this is what self.sending is for" well idk (im going insane)
    async def worker(self, chan):
        for i in self.matches:
            if self.captcha:
                await asyncio.sleep(1)
                continue

            print(f"sent: ww {i}")
            await self.owo_msg.reply(f"ww {i}")
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

        if message.channel.id == channel:
            if "⚠️" in message.content:
                self.captcha = True
                if self.index > 0:
                    self.index -= 1
                utils.log("Captcha Detected! ⚠️", "red")
                utils.notify(f"Captcha Detected!", f"Captcha - {self.user.name}!")

        if message.channel.id == self.owo_dm.id:
            if "👍" in message.content:
                self.captcha = False
                utils.log("Captcha Solved ✅", "green")

client = MyClient()
client.run(token)