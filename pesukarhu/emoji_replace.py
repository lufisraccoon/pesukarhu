import discord
from discord.ext import commands
from discord.ext.commands import bot
import re
import logging
import random

class EmojiReplace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logging.info(f'Initializing EmojiReplace')
        self.remove_non_alphanumeric = re.compile(r'([^\s\w]|_)+')
        self.emoji_replace = {
            'a': '🇦',
            'b': '🇧',
            'c': '🇨',
            'd': '🇩',
            'e': '🇪',
            'f': '🇫',
            'g': '🇬',
            'h': '🇭',
            'i': '🇮',
            'j': '🇯',
            'k': '🇰',
            'l': '🇱',
            'm': '🇲',
            'n': '🇳',
            'o': '🇴',
            'p': '🇵',
            'q': '🇶',
            'r': '🇷',
            's': '🇸',
            't': '🇹',
            'u': '🇺',
            'v': '🇻',
            'w': '🇼',
            'x': '🇽',
            'y': '🇾',
            'z': '🇿'
        }
        self.probability = [0, # 1 letter
                            0, # 2 letter
                            0, # 3 letter
                            0, # 4 letter
                            0.001, # 5 letter
                            0.002, # 6 letter
                            0.005, # 7 letter
                            0.01, # 8 letter
                            0.02, # 9 letter
                            0.03, # 10 letter
                            0.05, # 11 letter
                            0.1, # 12 letter
                            0.2, # 13 letter
                            0.3] # 14 letter

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            # don't respond to myself or other bots
            return

        if isinstance(message.channel, discord.channel.TextChannel):
            raw_message = message.content.lower()
            raw_message = self.remove_non_alphanumeric.sub('', raw_message)
            for word in raw_message.split():
                if(len(''.join(set(word))) == len(word)): # if all letters are unique
                    if((len(word) > len(self.probability)) or
                    (random.random() < self.probability[len(word)-1])):
                        logging.info(f'Found neat word - {word}')
                        for idx in range(0, len(word)):
                            await message.add_reaction(self.emoji_replace[word[idx]])
                        break # don't try to react to two words per message
            if("raccoon" in raw_message):
                await message.add_reaction('🦝')
