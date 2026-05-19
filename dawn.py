import threading
import aiohttp
import asyncio
import discord
import logging
import json
import pytz
import time
import sys
import re
import os

from discord.ext import tasks
from datetime import datetime, timedelta, timezone

import components_v2
import utils

on_mobile = utils.is_termux()
if not on_mobile:
    from playsound3 import playsound

# only error messages when critical
logging.getLogger("discord").setLevel(logging.CRITICAL)
logging.getLogger("discord.client").setLevel(logging.CRITICAL)
logging.getLogger("discord.state").setLevel(logging.CRITICAL)

lock = threading.Lock()

# TODO
# praying/curse detect if too early 
# if message.content = **⏱ | **! Slow down and try the command again **<t:1779153592:R>**)
# check if the this (timestamp - current timestamp) > 15 or 10 or else it could a battle too early
# then pray/curse again when the timestamp comes, simple, but it soooooo... far away

# steal auto use gems from echoquill

def clean(msg):
    return re.sub(r"[\W]", "", msg)

file = open("token.txt").read().strip().split()
token = file[0]

list_captcha = ["human", "captcha", "link", "letterword"]

settings = utils.load("settings.json")
data = utils.load("data.json")

ignoreGuilds = settings["bossBattle"]["ignoreGuilds"]
joinGuilds = settings["bossBattle"]["joinGuilds"]

cmds = settings["commands"]
cap = settings["captcha"]
prefix = cmds["prefix"]

if cap["image_solver"]:
    from captcha_solver.image_captcha import solveImageCaptcha

def progress(item):
    with lock:
        data["progress_lifetime"][item] += 1
        data["progress_today"][item] += 1
        utils.save("data.json", data)

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(enable_debug_events=True)

        self.watchdog_on_message = time.monotonic()
        self.watchdog_owo_message = time.monotonic()
        self.watchdog_battle_hunt = time.monotonic()
        self.watchdog_warned = False
        self.dawnPaused = False

        self.last_battle_hunt = time.monotonic()
        self.last_pray_curse = time.monotonic()

        self.last_open = time.monotonic()
        self.last_openBoss = time.monotonic()
        self.openCrates = False
        self.openBossCrates = False
        self.openLootboxes = False

        self.reccured = 0
        self.captcha = False
        self.channel = None
        self.owo_dm = None

        self.boss_tickets = 3
        self.joined_boss_ids = []
        self.sleeping = True

        self.session = None

    async def on_ready(self):
        utils.printBox(f"Logged in as {self.user}[*]", "purple")

        self.local_headers = await components_v2.headers.generate_headers()
        self.local_headers["Authorization"] = token
        if self.session is None:
            self.session = aiohttp.ClientSession()

        self.channel = self.get_channel(settings["channel"])

        self.inputer.start()
        self.farmer.start()
        self.watchdog.start()
        asyncio.create_task(self.time_check())
        
    def restart_code(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def on_disconnect(self):
        utils.notify("Paused Code", "on_disconnect")
        utils.log("on_disconnect() | Paused", "#00ffff")
        self.dawnPaused = True

    def on_resumed(self):
        utils.notify("Paused Code", "on_resumed")
        utils.log("on_resumed() | Resumed", "#00ffff")
        self.dawnPaused = False

    def watchdog_unpause(self):
        utils.log("Unpausing Code... ⚠️", "#00ffff")
        self.watchdog_on_message = time.monotonic()
        self.watchdog_owo_message = time.monotonic()
        self.watchdog_battle_hunt = time.monotonic()
        self.captcha = False
        self.watchdog_warned = False
        try:
            self.reccur_captcha.cancel()
        except:
            pass
        utils.log(f"Captcha: {self.captcha}", "#ffff00")
        utils.log(f"Watchdog Warned: {self.watchdog_warned}", "#ffff00")

    @tasks.loop()
    async def watchdog(self):
        now = time.monotonic()
        if self.captcha:
            self.watchdog_battle_hunt = time.monotonic()

        if self.watchdog_warned:
            return

        def watchdog_notify(wd_type):
            self.captcha = True
            self.watchdog_warned = True
            utils.log(f"Watchdog: {wd_type} Timeout, Pausing Code..", "red")
            utils.notify(f"{wd_type} Timeout, Pausing Code..", "Watchdog")

        if (now - self.watchdog_on_message) > 20:
            watchdog_notify("on_message()")

        if (now - self.watchdog_owo_message) > 30:
            watchdog_notify("OwO")

        if cmds["hunt"] or cmds["battle"]:
            if (now - self.watchdog_battle_hunt) > 40:
                watchdog_notify("Battle/Hunt")

    @tasks.loop(seconds=1)
    async def inputer(self):
        loop = asyncio.get_running_loop()
        key = await loop.run_in_executor(None, input)

        with lock:
            def toggle(obj, key, color):
                obj[key] = not obj[key]
                utils.log(f"{key}: {obj[key]}", color)

            match key:
                case "1": toggle(cmds, "battle", "purple")
                case "2": toggle(cmds, "hunt", "yellow")
                case "3": toggle(cmds, "owo", "#ffc0ff")
                case "4": 
                    cmds["pray"]["enabled"] = not cmds["pray"]["enabled"]
                    utils.log(f"pray: {cmds["pray"]["enabled"]}", "#00ffff")
                case "5": 
                    cmds["curse"]["enabled"] = not cmds["curse"]["enabled"]
                    utils.log(f"curse: {cmds["curse"]["enabled"]}", "#ff8000")
                case "6":
                    self.openCrates = not self.openCrates
                    utils.log(f"openCrates: {self.openCrates}", "#c1ff30")
                case "7":
                    self.openBossCrates = not self.openBossCrates
                    utils.log(f"openBossCrates: {self.openBossCrates}", "#c1ff30")
                case "8":
                    self.openLootboxes = not self.openLootboxes
                    utils.log(f"openLootboxes: {self.openLootboxes}", "#c1ff30")
                case "w": toggle(cap, "openWebsite", "#00ffc0")
                case "=":
                    cmds["cooldown"] += 0.25
                    utils.log(f"cooldown: {cmds["cooldown"]}", "#00ffc0")
                case "-":
                    cmds["cooldown"] -= 0.25
                    utils.log(f"cooldown: {cmds["cooldown"]}", "#00ffc0")
                case "c":
                    self.captcha = not self.captcha
                    utils.log(f"Captcha: {self.captcha}", "red")
                case "r":
                    self.watchdog_unpause()
                case "x":
                    sys.exit()
                case _:
                    utils.log(f"Invalid key: {key}", "white")

            utils.save("settings.json", settings)

    @tasks.loop()
    async def farmer(self):
        if self.captcha or self.dawnPaused or not self.channel:
            return

        now = time.time()

        async def send(cmd, log_color):
            utils.log(f"sent: {prefix+cmd}", log_color)
            await self.channel.send(prefix + cmd)

        if (now - self.last_battle_hunt > cmds["cooldown"]):
            self.last_battle_hunt = now
            if cmds["battle"]:
                await send("b", "purple")
            if cmds["hunt"]:
                await send("h", "yellow")
            if cmds["owo"]:
                utils.log("sent: owo", "#ffb0ff")
                await self.channel.send("owo")

        if (now - self.last_open >= 31):
            self.last_open = now
            if self.openCrates:
                await send("wc all", "#c0ff30")
            if self.openLootboxes:
                await send("lb all", "#c0ff30")
        if (now - self.last_openBoss >= 5.5):
            self.last_openBoss = now
            if self.openBossCrates:
                await send("use 99", "#c0ff30")

        if (now - self.last_pray_curse >= 303):
            self.last_pray_curse = now
            if cmds["pray"]["enabled"]:
                if cmds["pray"]["pingId"]:
                    await send(f"pray <@{cmds["pray"]["pingId"]}>")
                else:
                    await send("pray", "#00ffff")
            if cmds["curse"]["enabled"]:
                if cmds["curse"]["pingId"]:
                    await send(f"curse <@{cmds["curse"]["pingId"]}>")
                else:
                    await send("curse", "#ff8000")

    async def cap_hand(self):
        url = "https://owobot.com/captcha"

        if cap["notifications"]:
            time = datetime.now().strftime("%H:%M:%S")
            utils.notify(f"{time} - Captcha Detected", f"Captcha - {self.user.name}!")

        if cap["playAudio"]["enabled"]:
            path = cap["playAudio"]["path"]
            try:
                if on_mobile:
                    utils.run_system_command(
                        f"termux-media-player play {path}", timeout=5, retry=True
                    )
                else:
                    playsound(path, block=False)
            except Exception as e:
                print(f"{e} - at Audio")

        if cap["popup"]:
            try:
                if on_mobile:
                    utils.run_system_command(
                        f"termux-toast -c {"white"} -b {"black"} -g {"top"} '{"Captcha Detected"}'",
                        timeout=5,
                        retry=True,
                    )
            except Exception as e:
                print(f"{e} - at Popup")

        if cap["openWebsite"]:
            try:
                if on_mobile:
                    utils.run_system_command(f"termux-open {url}", timeout=5, retry=True)
                else:
                    if sys.platform.startswith("win"):
                        utils.run_system_command(f"start {url}", timeout=5, retry=True)
                    elif sys.platform == "darwin":
                        # Macos
                        run_system_command(f"open {url}", timeout=5, retry=True)
                    else:
                        # Linux
                        utils.run_system_command(f"xdg-open {url}", timeout=5, retry=True)
            except Exception as e:
                print(f"{e} - at openWebsite")

    @tasks.loop()
    async def reccur_captcha(self):
        self.reccured += 1
        utils.log(f"Captcha detected! ⚠️ {self.reccured}/10", "red")
        await self.cap_hand()

        if self.reccured >= 10:
            utils.log("Careful Twin ✌️", "yellow")
            try:
                self.reccur_captcha.cancel()
            except:
                pass

        await asyncio.sleep(60)

    async def on_message(self, message):
        self.watchdog_on_message = time.monotonic()
        if not self.channel:
            return

        if message.author.id == self.user.id:
            if message.content:
                if message.content == "owo":
                    progress("owos")
                    utils.log(f"😳 OwOs Today: {data['progress_today']['owos']}", "#ffffff")

        if not message.author.id == utils.id_owo:
            return
        self.watchdog_owo_message = time.monotonic()
        
        if not self.owo_dm:
            self.owo_dm = await message.author.create_dm()

        # captcha detection ($100000000)
        if message.channel.id == self.channel.id:
            components = message.components
            content = clean(message.content)

            has_verify_button = (
                components
                and components[0].children
                and getattr(components[0].children[0], "label", None) == "Verify"
                )

            has_warning_emoji = "⚠️" in message.content and message.attachments
            contains_captcha_word = any(word in content for word in list_captcha)

            if has_verify_button or has_warning_emoji or contains_captcha_word:
                if not any(
                    user in message.content for user in (
                        self.user.name,
                        f"<@{self.user.id}>",
                        self.user.display_name)
                        ):
                    return
                self.captcha = True
                image_captcha = False
                if message.attachments:
                    image_captcha = True
                if cap["reccur"]:
                    try:
                        self.reccured = 0
                        self.reccur_captcha.start()
                    except:
                        pass
                else:
                    utils.log("Captcha detected! ⚠️", "red")
                    await self.cap_hand()

                if cap["image_solver"] and image_captcha:
                    utils.log("Attempting to solve image captcha", "#656b66")
                    letters = int(re.findall(r"(\d+)(?=letterword)", content.lower())[0])
                    answer = await solveImageCaptcha(message.attachments[0].url, letters, self.session)
                    if answer:
                        utils.log(f"answer of image captcha -> {answer}", "#656b66")
                        await message.author.send(answer)

        # solved detection ($0.99)
        if message.channel.id == self.owo_dm.id and "👍" in message.content:
            self.captcha = False
            self.watchdog_warned = False # Is something wrong with this or Am I just paranoid that it might disable itself and ban me again
            progress("captchas")
            utils.log(f"Captcha solved! ✅ | Captchas: {data['progress_today']['captchas']}", "green")
            try:
                self.reccur_captcha.cancel()
            except:
                pass

        if message.channel.id == self.channel.id:
            # hunt result print
            if message.content:
                if f"**🌱 | {self.user.display_name}**" in message.content:
                    self.watchdog_battle_hunt = time.monotonic()

                    pattern = r"gained \*\*(\d+)xp\*\*!"
                    match = re.search(pattern, message.content)
                    if match:
                        xp = match.group(1)
                        progress("hunts")
                        utils.log(f"🌱 gained +{xp} xp | Hunts: {data['progress_today']['hunts']}", "#ffffff")

                # praying/cursing printing ling ingy
                if f"<@{self.user.id}>" in message.content:
                    if (f"<@{self.user.id}>** prays for " in message.content
                        or f"<@{self.user.id}>** prays..." in message.content
                        or f"<@{self.user.id}>** puts a curse on "in message.content
                        or f"<@{self.user.id}>** is now cursed." in message.content
                        # or "Slow down and try the command again" in message.content
                        ):
                        pattern = r"You have \*\*\d+\*\* luck point\(s\)!"
                        match = re.search(pattern, message.content)
                        if match:
                            result = match.group(0)
                            progress("prays_curses")
                            utils.log(f"{result} | prays/curses: {data['progress_today']['prays_curses']}", "#00ffff")

            # battle result print
            if message.embeds:
                for embed in message.embeds:
                    if (embed.author.name and f"{self.user.display_name} goes into battle!" in embed.author.name):
                        self.watchdog_battle_hunt = time.monotonic()
                        if embed.footer.text:
                            # https://pbs.twimg.com/media/G0fjkvAWUAA2JGQ.jpg
                            pattern = r"(won|lost|tie).*?(\d+).*?(\d[\d,]*)(?:.*?(\d[\d,]*))?"
                            match = re.search(pattern, embed.footer.text)
                            if match:
                                outcome = match.group(1)
                                turns = match.group(2)
                                xp = match.group(3) 
                                streak = match.group(4) if match.group(4) else "0"

                                result = f"⚔️  {outcome} | {turns} | {xp} | {streak}"
                                progress("battles")
                                utils.log(f"{result} | Battles: {data['progress_today']['battles']}", "#ffffff")

# [ ----------------------------------------------------------------- ]
# [ ---------------------- Boss Battle Section ---------------------- ]
# [ ----------------------------------------------------------------- ]

    def reset_boss_ticket(self, empty=False):
        if not empty:
            self.boss_tickets = 3
            data["boss_tickets"] = 3
            for k in data["progress_today"]:
                data["progress_today"][k] = 0
        else:
            self.boss_tickets = 0
            data["boss_tickets"] = 0

        print(f"reset_boss_ticket(empty: {empty}) | tickets: {self.boss_tickets}")
        utils.save("data.json", data)

    def consume_boss_ticket(self, revert=False):
        if not revert:
            self.boss_tickets -= 1
            data["boss_tickets"] -= 1
        else:
            self.boss_tickets += 1
            data["boss_tickets"] += 1
        
        print(f"consume_boss_ticket(revert: {revert}) | tickets: {self.boss_tickets}")

        utils.save("data.json", data)

    def calc_time(self):
        pst_timezone = pytz.timezone("US/Pacific")                              # get timezone
        pst_current_time = datetime.now(timezone.utc).astimezone(pst_timezone)  # get current time
        pst_midnight = pst_timezone.localize(datetime(                          # get owo reset time
                pst_current_time.year,
                pst_current_time.month,
                pst_current_time.day,
                0, 0, 0,
            )
        )
        time_until_owo_reset = (pst_midnight + timedelta(days=1) - pst_current_time) # owo reset time - current time
        total_seconds = time_until_owo_reset.total_seconds()                         # in seconds
        return total_seconds                                                         # done
        # w echoquill ❤️‍🩹 https://media1.tenor.com/m/q63zC0DgjDYAAAAd/ishowspeed-speed.gif

    def pst_midnight_ts(self):
        now = datetime.now(timezone.utc).astimezone(pytz.timezone("US/Pacific"))
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.timestamp()

    def return_battle_id(self, components):
        for component in components:
            if component.component_name == "media_gallery":
                media_item = component.items[0].media
                if "reward" in media_item.url:
                    return media_item.placeholder

        return None

    def should_join_guild(self, channel):
        if ignoreGuilds and channel.guild.id in ignoreGuilds:
            return False
        if joinGuilds and channel.guild.id not in joinGuilds:
            return False

        return True

    async def wait_till_reset_day(self):
        self.sleeping = True
        time_to_sleep = self.calc_time()
        utils.log(f"Sleeping boss battle till {time_to_sleep}", "#143B02")
        await asyncio.sleep(time_to_sleep)
        await self.time_check()
        self.sleeping = False

    async def time_check(self):
        self.boss_tickets = data["boss_tickets"]
        ts_last_reset = data["boss_last_reset"]

        if self.boss_tickets > 3 or self.boss_tickets < 0: # i dunno
            print("time check: invalid boss_tickets")
            self.reset_boss_ticket()

        ts_today_midnight = self.pst_midnight_ts()

        if not ts_last_reset or ts_last_reset < ts_today_midnight:
            print("time check: resetting tickets and last_reset")
            self.reset_boss_ticket()
            data["boss_last_reset"] = ts_today_midnight

            utils.save("data.json", data)

        self.sleeping = False

    async def on_socket_raw_receive(self, msg):
        if not settings["bossBattle"]["enabled"]:
            return

        if self.boss_tickets <= 0 or self.sleeping:
            if not self.sleeping:
                utils.log("Not enough boss tickets to join boss battle..", "#143B02")
                await self.wait_till_reset_day()
            return

        parsed_msg = json.loads(msg)
        if parsed_msg.get("t") != "MESSAGE_CREATE":
            return

        message = components_v2.message.get_message_obj(parsed_msg["d"])

        if message.author.id == utils.id_owo:
             if message.components:
                for comps in message.components:
                    if comps.component_name == "section":
                        if (comps.components[0].content and "runs away" in comps.components[0].content):
                            battle_id = self.return_battle_id(message.components)
                            if not battle_id or battle_id in self.joined_boss_ids:
                                return
                            else:
                                self.joined_boss_ids.append(battle_id)

                            if (comps.accessory and comps.accessory.component_name == "button"):
                                if comps.accessory.custom_id == "guildboss_fight":
                                    boss_channel = await self.fetch_channel(message.channel_id)
                                    if boss_channel and self.should_join_guild(boss_channel):
                                        await asyncio.sleep(1)
                                        if not self.captcha:
                                            click_status = (
                                                await comps.accessory.click(
                                                    self.ws.session_id,
                                                    self.local_headers,
                                                    boss_channel.guild.id,
                                                )
                                            )
                                            if click_status:
                                                utils.log(
                                                    f"Joined Boss battle! -> {boss_channel.guild.name} - {boss_channel.name}", "#B5C1CE")
                                                self.consume_boss_ticket()

                    if comps.component_name == "text_display":
                        if "Are you sure you want to use another boss ticket?" in comps.content:
                            utils.log("Boss battle was already joined.", "#B5C1CE")
                            self.consume_boss_ticket(revert=True)

                        if "You don't have any boss tickets!" in comps.content:
                            utils.log("You don't have any boss tickets!", "#B5C1CE")
                            self.reset_boss_ticket(empty=True)
                            self.joined_boss_ids = []

client = MyClient()
client.run(token)