import subprocess
import threading
import requests
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
import shutil

on_mobile = utils.is_termux()
if not on_mobile:
    try:
        from playsound3 import playsound
    except Exception:
        playsound = None

    try:
        import winsound
    except Exception:
        winsound = None

    def _play_system_sound_once():
        try:
            if winsound and sys.platform.startswith("win"):
                winsound.Beep(1000, 200)
                return True
            if sys.platform == "darwin":
                if shutil.which("afplay"):
                    os.system("afplay /System/Library/Sounds/Glass.aiff >/dev/null 2>&1")
                    return True
                # fallback to osascript beep
                if shutil.which("osascript"):
                    os.system("osascript -e 'beep' >/dev/null 2>&1")
                    return True
            if sys.platform.startswith("linux"):
                if shutil.which("paplay"):
                    os.system("paplay /usr/share/sounds/freedesktop/stereo/complete.oga >/dev/null 2>&1")
                    return True
                if shutil.which("aplay"):
                    os.system("aplay /usr/share/sounds/alsa/Front_Center.wav >/dev/null 2>&1")
                    return True
                if shutil.which("beep"):
                    os.system("beep >/dev/null 2>&1")
                    return True
            # generic terminal bell fallback
            print('\a', end='', flush=True)
            return True
        except Exception:
            try:
                print('\a', end='', flush=True)
            except Exception:
                pass
            return False

    def Beep(times=1, freq=1000, duration=200):
        for i in range(times):
            try:
                if winsound and sys.platform.startswith("win"):
                    winsound.Beep(freq, duration)
                else:
                    played = _play_system_sound_once()
                    if not played and playsound:
                        try:
                            playsound.__call__("", block=False)
                        except Exception:
                            pass
            except Exception:
                try:
                    _play_system_sound_once()
                except Exception:
                    pass
            time.sleep(duration / 1000.0)
else:
    def Beep(a, b, c):
        return

# only error messages when critical
# logging.getLogger("discord").setLevel(logging.CRITICAL)
# logging.getLogger("discord.client").setLevel(logging.CRITICAL)
# logging.getLogger("discord.state").setLevel(logging.CRITICAL)

lock = threading.Lock()

token = open("token.txt").read().strip()

list_captcha = ["human", "captcha", "link", "letterword"]

settings = utils.load("settings.json")
stats = utils.load("stats.json")

owo_prefix = settings["commands"]["prefix"]

if settings["captcha"]["image_solver"]:
    from captcha_solver.image_captcha import solveImageCaptcha

gem_tiers = {
    "common": ["051", "065", "072", "079"],
    "uncommon": ["052", "066", "073", "080"],
    "rare": ["053", "067", "074", "081"],
    "epic": ["054", "068", "075", "082"],
    "mythical": ["055", "069", "076", "083"],
    "legendary": ["056", "070", "077", "084"],
    "fabled": ["057", "071", "078", "085"],
}

def convert_small_numbers(small_number):
    numbers = {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
    }
    normal_string = "".join(numbers.get(char, char) for char in small_number)
    return int(normal_string)

def find_gems_available(message):
    print("find_gems_available")
    available_gems = {
        "fabled": {"057": 0, "071": 0, "078": 0, "085": 0},  # fabled
        "legendary": {"056": 0, "070": 0, "077": 0, "084": 0},  # legendary
        "mythical": {"055": 0, "069": 0, "076": 0, "083": 0},  # mythical
        "epic": {"054": 0, "068": 0, "075": 0, "082": 0},  # epic
        "rare": {"053": 0, "067": 0, "074": 0, "081": 0},  # rare
        "uncommon": {"052": 0, "066": 0, "073": 0, "080": 0},  # uncommon
        "common": {"051": 0, "065": 0, "072": 0, "079": 0},  # common
        # hunt, emp, luck, special
    }
    inv_numbers = re.findall(r"`(\d+)`.*?([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", message)
    for gem_id, small_number in inv_numbers:
        gem_count = convert_small_numbers(small_number)

        for _, gems in available_gems.items():
            if gem_id in gems:
                gems[gem_id] = gem_count
                break
    return available_gems

def restart(): # unused for now
    os.execv(sys.executable, [sys.executable] + sys.argv)

def clean(msg):
    return re.sub(r"[\W]", "", msg)

def progress(item):
    with lock:
        stats["progress_lifetime"][item] += 1
        stats["progress_today"][item] += 1
        utils.save("stats.json", stats)

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(enable_debug_events=True)

        # Watchdog
        self.watchdog_on_message = time.monotonic()
        self.watchdog_owo_message = time.monotonic()
        self.watchdog_battle_hunt = time.monotonic()
        self.watchdog_warned = False
        self.last_beep = 0

        # Commands
        self.last_battle_hunt = 0
        self.last_pray_curse = 0

        # Auto Crates/Lootboxes
        self.last_open = time.monotonic()
        self.last_openBoss = time.monotonic()
        self.openCrates = False
        self.openBossCrates = False
        self.openLootboxes = False

        self.reccured = 0
        self.captcha = False
        self.channel = None
        self.owo_dm = None

        # Auto Boss Battle
        self.boss_tickets = 3
        self.joined_boss_ids = []
        self.sleeping = True

        # Auto Gems
        self.no_gems = False
        self.available_gems = {}
        self.inventory_check = False

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

    async def on_disconnect(self):
        if not self.watchdog_warned:
            utils.notify("Paused!", "on_disconnect")
            utils.log("▶️ on_disconnect() | Paused!", "#00ffff")
            Beep(1, 1000, 150)
            self.watchdog_warned = True

    async def on_resumed(self):
        # utils.notify("Resumed!", "on_resumed")
        utils.log("⏸️ on_resumed() | Resumed!", "#00ffff")
        self.watchdog_warned = False
        Beep(2, 500, 75)

    def watchdog_unpause(self):
        utils.log("⏸️ Resuming...", "#00ffff")
        self.watchdog_on_message = self.watchdog_owo_message = self.watchdog_battle_hunt = time.monotonic()
        self.watchdog_warned = False
        self.captcha = False
        try:
            self.reccur_captcha.cancel()
        except:
            pass

    def watchdog_notify(self, wd_type):
        self.watchdog_warned = True
        utils.log(f"▶️ Watchdog: {wd_type} Timeout, Paused!", "red")
        utils.notify(f"▶️ {wd_type} Timeout, Paused!", "Watchdog")

    @tasks.loop()
    async def watchdog(self):
        now = time.monotonic()
        if self.captcha:
            self.watchdog_battle_hunt = time.monotonic()

        if self.watchdog_warned:
            if not self.last_beep:
                self.last_beep = time.monotonic()
            if (now - self.last_beep) >= 60:
                Beep(2, 500, 100)
                self.last_beep = time.monotonic()
            return

        if (now - self.watchdog_on_message) >= 20:
            self.watchdog_notify("on_message()")

        if (now - self.watchdog_owo_message) >= 30:
            self.watchdog_notify("OwO")

        if settings["commands"]["hunt"] or settings["commands"]["battle"]:
            if (now - self.watchdog_battle_hunt) >= 40:
                self.watchdog_notify("Battle/Hunt")

    @tasks.loop(seconds=1)
    async def inputer(self):
        loop = asyncio.get_running_loop()
        key = await loop.run_in_executor(None, input)

        with lock:
            def toggle(obj, key,  name, color):
                if isinstance(obj, dict):
                    obj[key] = not obj[key]
                    val = obj[key]
                else:
                    setattr(obj, key, not getattr(obj, key))
                    val = getattr(obj, key)

                utils.log(f"{name}: {val}", color)

            match key:
                case "1": toggle(settings["commands"], "battle", "Auto Battle", "purple")
                case "2": toggle(settings["commands"], "hunt", "Auto Hunt", "yellow")
                case "3": toggle(settings["commands"], "owo", "Auto OwO", "#ffc0ff")
                case "4": toggle(settings["commands"]["pray"], "enabled", "Auto Pray", "#00ffff")
                case "5": toggle(settings["commands"]["curse"], "enabled", "Auto Curse", "#ff8000")
                case "6": toggle(self, "openCrates", "Auto Crates", "#c1ff30")
                case "7": toggle(self, "openBossCrates", "Auto Boss Crates", "#c1ff30")
                case "8": toggle(settings["commands"]["autoUseGems"], "enabled", "Auto Gems", "#8b25ff")
                case "9": toggle(settings["commands"]["autoUseGems"], "lowestToHighest", "Lowest To Highest", "#8b25ff")
                case "0": toggle(settings["commands"]["autoUseGems"], "partialCombinations", "Partial Combinations", "#8b25ff")
                case "w": toggle(settings["captcha"], "openWebsite", "Open Website", "#00ffc0")
                case "c": toggle(self, "captcha", "Paused", "red")
                case "=":
                    settings["commands"]["cooldown"] += 0.25
                    utils.log(f"cooldown: {settings['commands']['cooldown']}", "#00ffc0")
                case "-":
                    settings["commands"]["cooldown"] -= 0.25
                    utils.log(f"cooldown: {settings['commands']['cooldown']}", "#00ffc0")
                case "r": self.watchdog_unpause()
                case "p": await self.cap_handler()
                case "x": os._exit(1)
                case _: utils.log(f"Invalid key: {key}", "white")

            utils.save("settings.json", settings)

    async def send(self, cmd, color, use_prefix=True):
        if use_prefix:
            utils.log(f"sent: {owo_prefix + cmd}", color)
            await self.channel.send(owo_prefix + cmd)
        else:
            utils.log(f"sent: {cmd}", color)
            await self.channel.send(cmd)

    @tasks.loop()
    async def farmer(self):
        if self.captcha or self.watchdog_warned or not self.channel:
            return

        now = time.monotonic()

        if (now - self.last_battle_hunt) > settings["commands"]["cooldown"]:
            self.last_battle_hunt = now
            if settings["commands"]["battle"]:
                await self.send("b", "purple")
            if settings["commands"]["hunt"]:
                await self.send("h", "#ffff00")
            if settings["commands"]["owo"]:
                await self.send("owo", "#ffc0ff", False)

        if (now - self.last_open) >= 31:
            self.last_open = now
            if self.openCrates:
                await self.send("wc all", "#c0ff30")

        if (now - self.last_openBoss) >= 5.5:
            self.last_openBoss = now
            if self.openBossCrates:
                await self.send("use 99", "#c0ff30")

        if (now - self.last_pray_curse) >= 300:
            self.last_pray_curse = now
            if settings["commands"]["pray"]["enabled"]:
                if settings["commands"]["pray"]["pingId"]:
                    await self.send(f"pray <@{settings["commands"]["pray"]["pingId"]}>", "#00ffff")
                else:
                    await self.send("pray", "#00ffff")
            if settings["commands"]["curse"]["enabled"]:
                if settings["commands"]["curse"]["pingId"]:
                    await self.send(f"curse <@{settings["commands"]["curse"]["pingId"]}>", "#ff8000")
                else:
                    await self.send("curse", "#ff8000")

    async def cap_handler(self):
        url = "https://owobot.com/captcha"
        current_step = "Initializing"

        try:
            if settings["captcha"]["notifications"]:
                current_step = "Sending Notification"
                time_str = datetime.now().strftime("%H:%M:%S")
                utils.notify(f"{time_str} - Captcha Detected", f"Captcha - {self.user.name}!")

            if settings["captcha"]["playAudio"]["enabled"]:
                current_step = "Playing Audio"
                path = settings["captcha"]["playAudio"]["path"]
                if on_mobile:
                    utils.run_system_command(f"termux-media-player play {path}", timeout=3, retry=True)
                else:
                    playsound(path, block=False)

            if settings["captcha"]["popup"]:
                current_step = "Displaying Popup"
                if on_mobile:
                    utils.run_system_command(f"termux-toast -c 'white' -b 'black' -g 'top' 'Captcha Detected'", timeout=3, retry=True)

            if settings["captcha"]["openWebsite"]:
                current_step = "Opening Website"

                if on_mobile:
                    utils.run_system_command(f"termux-open {url}", timeout=5, retry=True)
                else:
                    if sys.platform.startswith("win"):
                        utils.run_system_command(f"start {url}", timeout=5, retry=True)
                    elif sys.platform == "darwin":
                        # Macos
                        utils.run_system_command(f"open {url}", timeout=5, retry=True)
                    else:
                        # Linux
                        utils.run_system_command(f"xdg-open {url}", timeout=5, retry=True)

        except Exception as e:
            print(f"{e} - at {current_step}")

    @tasks.loop()
    async def reccur_captcha(self):
        self.reccured += 1
        utils.log(f"Captcha detected! ⚠️ {self.reccured}/10", "red")
        await self.cap_handler()

        await asyncio.sleep(60)

    def get_nick(self, msg):
        if not msg.guild:
            return ""
        else:
            user = msg.guild.me
            if user.nick:
                return user.nick
            elif user.display_name:
                return user.display_name
            else:
                return user.name

    async def on_message(self, message):
        self.watchdog_on_message = time.monotonic()

        if not self.channel:
            return

        if message.author.id == self.user.id:
            if message.content:
                if message.content == "owo":
                    progress("owos")
                    # utils.log(f"😳 OwOs Today: {stats['progress_today']['owos']}", "#ffffff")

        if not message.author.id == utils.id_owo:
            return # from here and below anything that isnt from owo is ignored

        self.watchdog_owo_message = time.monotonic()

        if not self.owo_dm:
            self.owo_dm = await message.author.create_dm()

        # captcha detection ($1.000.000)
        if message.channel.id == self.channel.id:
            components = message.components
            content = clean(message.content)

            has_verify_button = (components and components[0].children and getattr(components[0].children[0], "label", None) == "Verify")
            has_warning_emoji = "⚠️" in message.content and message.attachments
            contains_captcha_word = any(word in content for word in list_captcha)

            if has_verify_button or has_warning_emoji or contains_captcha_word:
                if not any(user in message.content for user in (self.user.name, f"<@{self.user.id}>", self.user.display_name)):
                    return
                self.captcha = True
                image_captcha = False
                if message.attachments:
                    image_captcha = True
                if settings["captcha"]["reccur"]:
                    try:
                        self.reccured = 0
                        self.reccur_captcha.start()
                    except:
                        pass
                else:
                    utils.log("Captcha detected! ⚠️", "red")
                    await self.cap_handler()

                if settings["captcha"]["image_solver"] and image_captcha:
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
            Beep(2, 1500, 75)
            utils.log(f"Captcha solved! ✅ | Captchas: {stats['progress_today']['captchas']}", "green")
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
                        utils.log(f"🌱 gained +{xp} xp | Hunts: {stats['progress_today']['hunts']}", "#ffffff")

                # praying/cursing printing ling ingy
                if f"<@{self.user.id}>" in message.content:
                    if (f"<@{self.user.id}>** prays for " in message.content
                        or f"<@{self.user.id}>** prays..." in message.content
                        or f"<@{self.user.id}>** puts a curse on "in message.content
                        or f"<@{self.user.id}>** is now cursed." in message.content
                        ):
                        pattern = r"You have \*\*\d+\*\* luck point\(s\)!"
                        match = re.search(pattern, message.content)
                        if match:
                            result = match.group(0)
                            progress("prays_curses")
                            utils.log(f"{result} | prays/curses: {stats['progress_today']['prays_curses']}", "#00ffff")

                if "Slow down and try the command again" in message.content:
                    slowdown_match = re.search(r"<t:(\d+):[Rr]>", message.content)
                    if slowdown_match:
                        try:
                            slowdown_ts = int(slowdown_match.group(1))
                            now_ts = time.time()
                            delta = slowdown_ts - now_ts
                            if delta > 10:
                                self.last_pray_curse = time.monotonic() + delta - 300
                                print(f"Pray too early, retrying in: {delta}s")
                            elif delta <= 300:
                                self.last_battle_hunt = time.monotonic() + delta - 15
                                print(f"Battle too early, retrying in: {delta}s")
                        except Exception:
                            pass

                # auto use gems
                if not settings["commands"]["autoUseGems"]["enabled"]:
                    return

                nick = self.get_nick(message)
                if nick not in message.content:
                    return

                if "caught" in message.content:
                    if self.no_gems:
                        utils.log("No gems", "#fa6b28")
                        return
                    await asyncio.sleep(3)
                    self.inventory_check = True
                    await self.send("inv", "#7700ff")

                elif "'s Inventory ======**" in message.content:
                    self.available_gems = find_gems_available(message.content)
                    if self.inventory_check:
                        await self.use_gems(self.available_gems)
                        self.inventory_check = False

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
                                utils.log(f"{result} | Battles: {stats['progress_today']['battles']}", "#ffffff")

# [ ----------------------------------------------------------------- ]
# [ ----------------------- Auto Gems Section ----------------------- ]
# [ ----------------------------------------------------------------- ]

    async def use_gems(self, available_gems):
        result = self.find_gems_to_use(available_gems)
        if result:
            gems_to_use = ""
            for item in result:
                gems_to_use += f"{item[1:]} "

            await asyncio.sleep(3)
            text = f"use {gems_to_use}"
            await self.send(text, "#25aaff")
            self.reduce_used_gems(result)
        else:
            utils.log("Warn: No gems to use.", "#924444")
            self.no_gems = True

    def reduce_used_gems(self, used_gem_ids):
        for gem_id in used_gem_ids:
            for _, gems in self.available_gems.items():
                if gem_id in gems:
                    if gems[gem_id] > 0:
                        gems[gem_id] -= 1
                    if gems[gem_id] < 0:
                        # Huh?
                        gems[gem_id] = 0
                    break

    def find_gems_to_use(self, available_gems):
        gem_type = {0: "huntGem", 1: "empoweredGem", 2: "luckyGem", 3: "specialGem"}
        tier_order = [
            "fabled",
            "legendary",
            "mythical",
            "epic",
            "rare",
            "uncommon",
            "common",
        ]
        cnf = settings["commands"]["autoUseGems"]

        if cnf["lowestToHighest"]:
            tier_order.reverse()

        grouped_gem_list = []
        required_gems_count = sum(1 for enabled in cnf["gemsToUse"].values() if enabled)

        for tier in tier_order:
            if not cnf["tiers"][tier]:
                continue

            current_group = []
            for gem_id in gem_tiers[tier]:
                gem_index = gem_tiers[tier].index(gem_id)
                gem_type_key = gem_type[gem_index]
                if (cnf["gemsToUse"].get(gem_type_key) and available_gems[tier].get(gem_id, 0) > 0):
                    current_group.append(gem_id)

            if current_group:
                if not cnf["partialCombinations"] and len(current_group) < required_gems_count:
                    continue
                grouped_gem_list.append(current_group)

        return self.process_result(grouped_gem_list)

    def process_result(self, result):
        # Find the group with the highest number of items
        max_group = max(result, key=len, default=None)
        return max_group

# [ ----------------------------------------------------------------- ]
# [ ---------------------- Boss Battle Section ---------------------- ]
# [ ----------------------------------------------------------------- ]

    def reset_boss_ticket(self, empty=False):
        self.boss_tickets = 0 if empty else 3
        stats["boss_tickets"] = 0 if empty else 3
        if not empty:
            for k in stats["progress_today"]:
                stats["progress_today"][k] = 0

        utils.save("stats.json", stats)
        print(f"reset_boss_ticket(empty: {empty}) | tickets: {self.boss_tickets}")

    def consume_boss_ticket(self, revert=False):
        self.boss_tickets -= 1 if revert else +1
        stats["boss_tickets"] -= 1 if revert else +1
        utils.save("stats.json", stats)
        print(f"consume_boss_ticket(revert: {revert}) | tickets: {self.boss_tickets}")

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

    def owo_last_reset_timestamp(self):
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
        if settings["bossBattle"]["ignoreGuilds"] and channel.guild.id in settings["bossBattle"]["ignoreGuilds"]:
            return False
        if settings["bossBattle"]["joinGuilds"] and channel.guild.id not in settings["bossBattle"]["joinGuilds"]:
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
        self.boss_tickets = stats["boss_tickets"]
        current_last_reset = stats["boss_last_reset"]

        if self.boss_tickets > 3 or self.boss_tickets < 0: # i dunno
            print("time check: invalid boss_tickets")
            self.reset_boss_ticket()

        owo_last_reset = self.owo_last_reset_timestamp()

        if not current_last_reset or current_last_reset < owo_last_reset:
            print("time check: resetting tickets and last_reset")
            self.reset_boss_ticket()
            stats["boss_last_reset"] = owo_last_reset

            utils.save("stats.json", stats)

        self.sleeping = False

    async def on_socket_raw_receive(self, msg):
        if not settings["bossBattle"]["enabled"]:
            return

        if self.boss_tickets <= 0 or self.sleeping:
            if not self.sleeping:
                utils.log("Not enough boss tickets (stats.json)..", "#143B02")
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
                            utils.log("You don't have any boss tickets (Message)!", "#B5C1CE")
                            self.reset_boss_ticket(empty=True)
                            self.joined_boss_ids = []

client = MyClient()
client.run(token)