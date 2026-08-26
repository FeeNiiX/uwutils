import discord
import rich
import re

import dumper

token = open("token.txt").read().strip()
minimum_streak = 100000
max_level = 70
messages = 1000

def filter(description: str):
    # total_emojis = len(re.findall(r'<a?:\w+:\d+>', description))
    # if total_emojis > 4:
    #     return None
    cleaned = re.sub(r'<a?:(\w+):\d+>', r'\1 ', description)
    cleaned = cleaned.replace('**', '')

    lines = cleaned.split('\n')
    final_lines = []

    for line in lines:

        if not line.strip():
            print("not line.strip", line)
            continue

        words = line.split()

        if not len(words) == 8: # len starts at 1, words[index] starts at 0
            return None

        level = words[0]
        animal_emoji = words[1]
        animal_name = words[2]
        pipe = words[3]
        rarity = words[4]
        weapon = words[5]
        passive = words[6]
        percentage = words[7]

        clean_level = int(level[2:])
        clean_weapon = weapon[1:].capitalize()
        clean_passive = passive[1:].capitalize()

        if clean_level > max_level:
            return None

        new_line = f"{level} {animal_emoji} {pipe} {clean_weapon} {clean_passive} {percentage}"
        final_lines.append(new_line)

    return '\n'.join(final_lines)

class MyClient(discord.Client):
    async def on_ready(self):
        print("Ready")
        neon = self.get_user(851436490415931422)
        guild = self.get_guild(988560881019392050)
        i = 0

        async for message in guild.search('Global Simulation Results', has=['embed'], authors=[neon], limit=messages):
            i += 1; print("messages: ", i, end='\r', flush=True)
            if message.embeds:
                for embed in message.embeds:
                    if embed.footer and embed.footer.text and embed.description:
                        if "Average streak: " in embed.footer.text:
                            match = re.search(r"Average streak: (\d+)", embed.footer.text)
                            if match:
                                average = int(match.group(1))
                                if average > minimum_streak:
                                    filtered_desc = filter(embed.description)

                                    if filtered_desc:
                                        rich.print(f"{filtered_desc}\nAverage Streak: {average:,} -> [link={message.jump_url}]Jump to Message[/link]\n")

        await self.close()

client = MyClient()
client.run(token)