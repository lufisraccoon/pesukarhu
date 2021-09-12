#!/usr/bin/env python3
# bot.py
import os
import logging
import discord
from discord.ext import tasks
from discord.ext import commands
import pesukarhu.member_monitor
import pesukarhu.emoji_replace

from dotenv import load_dotenv

load_dotenv()
token = os.getenv('PESUKARHU_TOKEN')

intents = discord.Intents.all()
logging.basicConfig(format='%(asctime)s %(levelname)s {%(module)s} [%(funcName)s] %(message)s', datefmt='%Y%m%d|%H:%M:%S', level=logging.INFO)
bot = commands.Bot(command_prefix="$", intents=intents)
bot.add_cog(pesukarhu.member_monitor.MemberMonitor(bot))
bot.add_cog(pesukarhu.emoji_replace.EmojiReplace(bot))
bot.run(token)