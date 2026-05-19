import discord
import asyncio
import logging
import json
from rich.pretty import pprint

import components_v2
import dumper
import utils

file = open("token.txt").read().strip().split()
token = file[0]
channel = file[1]

logging.getLogger("discord").setLevel(logging.CRITICAL)
logging.getLogger("discord.client").setLevel(logging.CRITICAL)
logging.getLogger("discord.state").setLevel(logging.CRITICAL)

# TODO
# reroll stats implementantion (compare [current] % with [new] % and if its bigger done)
# or actually see if the base stats rerolled was better, maybe with neonutil help

####################
## CONFIG SECTION ##
####################

best_qualities = {"l", "f"}
all_passives = {
    "lwolf", "adapt", "dstrike", "frarm", "gslay", "resonance",
    "hgen", "wgen", "hp", "wp", "pr", "mr", "sprout", "kkaze", "thorns",
    "att", "mag", "manatap", "critical", "lifesteal", "enrage", "snail",
    "sac", "safeguard", "discharge", "absolve", "kno"
}
fableds = {q + p for q in best_qualities for p in all_passives}
# in case you get a good passive that you forgot to choose

weapons = {
    "mag_damage":       {"mag", "sac", "manatap", "safeguard", "discharge", "gslay", "critical", "lifesteal", "enrage"},
    "att_damage":       {"att", "sac", "manatap", "safeguard", "discharge", "gslay", "critical", "lifesteal", "enrage"},
    "shield_rstaff":    {"hgen", "wgen", "sac", "safeguard","discharge", "kkaze", "sprout", "frarm", "thorns"},
    "pstaff":           {"hgen", "wgen", "sac", "discharge", "thorns", "manatap", "frarm", "dstrike"},
    "crune":            {"pr", "hgen", "wgen", "safeguard", "discharge", "thorns"}
}
# c | u | r | e | m | l | f
custom_qualities = {"m"}
custom_passives = {"kno"} | weapons["pstaff"]
custom = {q + p for q in custom_qualities for p in custom_passives}

final =  fableds | custom

# pprint(final)

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(enable_debug_events=True)

    async def on_ready(self):
        utils.printBox(f'Logged in as {self.user}', "#f0f0f0")
        self.local_headers = await components_v2.headers.generate_headers()
        self.local_headers["Authorization"] = token

    async def on_socket_raw_receive(self, msg):
        parsed_msg = json.loads(msg)
        if parsed_msg["t"] not in ("MESSAGE_UPDATE", "MESSAGE_CREATE"):
            return
        message = components_v2.message.get_message_obj(parsed_msg["d"])

        if message.channel_id != channel:
            return
        chann = self.get_channel(channel)

        if message.author.id == utils.id_neonutil or message.author.id == utils.id_owo:
            if message.buttons:
                for i in message.buttons:
                    if i.emoji.name in ("check", "close", "weaponshard", "sync"):
                        if i.emoji.name == "sync":
                            btn = i

            if message.components:
                for i in message.components:
                    if "[NEW]" in i.content:
                        cont = i.content

            if not cont and not btn:
                print("No Components and Buttons")
                return

            match = next((a for a in final if a in cont), None)

            if not match:
                try:
                    await asyncio.sleep(0.25)
                    if not btn.disabled:
                        await btn.click(self.ws.session_id, self.local_headers, chann.guild.id)
                    else:
                        print("Button Disabled")
                except Exception as e:
                    print("Error: ", e)
            else:
                print(f"Found: {match}")



client = MyClient()
client.run(token)