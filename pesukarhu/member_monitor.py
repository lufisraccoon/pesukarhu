import os
import discord
import datetime
from discord.ext import commands
from discord.ext import tasks
from discord.ext.commands import bot
from dotenv import load_dotenv
import logging
import enum
import pytimeparse.timeparse

class MemberMonitor(commands.Cog):
    class MemberState(enum.Enum):
        UNVERIFIED = enum.auto()
        WARNED = enum.auto()
        VERIFIED = enum.auto()
        REMOVED = enum.auto()

    class Member():
        '''
        Stores info about users who joined. name is at entry time; may not be
        accurate if user changes their name. ID is assumed to be the key for
        a dictionary storing Members, so its not explicitly stored as part of
        the Member object.
        '''
        def __init__(self, name, warn_time_offset, kick_time_offset):
            current_time = datetime.datetime.now()
            self.name = name
            self.add_time = current_time
            self.warn_time = current_time + warn_time_offset
            self.kick_time = current_time + kick_time_offset
            self.trim_retention_time = None # to be filled in later
            self.state = MemberMonitor.MemberState.UNVERIFIED

    class MemberList():
        def __init__(self):
            self.member_list = {}
            self.warn_delay = float(os.getenv('PESUKARHU_UNVERIFIED_WARN_DELAY'))
            self.kick_delay = float(os.getenv('PESUKARHU_UNVERIFIED_KICK_DELAY'))
            self.retention_time = float(os.getenv('PESUKARHU_RETENTION_TIME'))
            logging.info(f'Initializing MemberList:')
            logging.info(f'   warn delay = {self.warn_delay} (sec)')
            logging.info(f'   kick delay = {self.kick_delay} (sec)')
            logging.info(f'   retention_time = {self.retention_time} (sec)')
            # Convert to timedeltas for math purposes
            self.warn_delay = datetime.timedelta(0, self.warn_delay)
            self.kick_delay = datetime.timedelta(0, self.kick_delay)
            self.retention_time = datetime.timedelta(0, self.retention_time)

        def add_member(self, id, name):
            logging.info(f'Added: {id} - {name}')
            self.member_list[id] = MemberMonitor.Member(name, self.warn_delay, self.kick_delay)
    
        def remove_member(self, id):
            logging.info(f'Deleted: {id} - {self.member_list[id].name}')
            del self.member_list[id]

        def set_removed_state(self, id):
            current_time = datetime.datetime.now()
            logging.info(f'Set removed: {id} - {self.member_list[id].name}')
            self.member_list[id].state = MemberMonitor.MemberState.REMOVED
            self.member_list[id].trim_retention_time = current_time + self.retention_time

        def verify_member(self, id):
            current_time = datetime.datetime.now()
            logging.info(f'Verified: {id} - {self.member_list[id].name}')
            self.member_list[id].state = MemberMonitor.MemberState.VERIFIED
            self.member_list[id].trim_retention_time = current_time + self.retention_time

        def unverify_member(self, id, name):
            current_time = datetime.datetime.now()
            if(id in self.member_list.keys()):
                logging.info(f'Unverified: {id} - {self.member_list[id].name}')
                self.member_list[id].state = MemberMonitor.MemberState.UNVERIFIED
                self.member_list[id].add_time = current_time
                self.member_list[id].warn_time = current_time + self.warn_delay
                self.member_list[id].kick_time = current_time + self.kick_delay
            else:
                # Was not in recent joins list, have to add them
                logging.info(f'Unverified: {id} - {name}')
                self.add_member(id, name)

        def warn_member(self, id):
            logging.info(f'Warned: {id} - {self.member_list[id].name}')
            self.member_list[id].state = MemberMonitor.MemberState.WARNED

        def trim_unmonitored_members(self):
            current_time = datetime.datetime.now()
            # Create a copy here so that the member_list dict doesn't change
            # size during iteration
            for key, member in self.member_list.copy().items():
                if(((member.state == MemberMonitor.MemberState.REMOVED) or
                    (member.state == MemberMonitor.MemberState.VERIFIED)) and
                   (member.trim_retention_time <= current_time)):
                   self.remove_member(key)

        def count_recent_joins(self, time_window):
            # This could probably be done with a list comprehension
            current_time = datetime.datetime.now()
            count = 0
            for key, member in self.member_list.items():
                age = current_time - member.add_time
                if(age.total_seconds() < time_window):
                    count += 1
            return count

        def get_embed(self):
            current_time = datetime.datetime.now()
            if(len(self.member_list) == 0):
                id_string = "Empty"
                add_string = "Empty"
                state_string = "Empty"
            else:
                id_string = ""
                add_string = ""
                state_string = ""

                for key, member in self.member_list.items():
                    age = current_time - member.add_time # as timedelta object
                    age = age.total_seconds() # as float
                    new_id = f'{key} ({member.name})\n'
                    new_add = f'{member.add_time.strftime("%Y%m%d|%H:%M:%S")} ({age:.0f})\n'
                    new_state = f'{member.state.name.capitalize()}\n'
                    # Check to make sure we don't exceed 1024 characters per field. We
                    # won't hit the 6000 character total limit
                    if((len(id_string) + len(new_id) <= 1000) and \
                       (len(add_string) + len(new_add) <= 1000) and \
                       (len(state_string) + len(new_state) <= 1000)):
                        id_string += new_id
                        add_string += new_add
                        state_string += new_state
                    else:
                        break
            embed=discord.Embed(title=f'Recent join list: ({len(self.member_list)} members)')
            embed.add_field(name="ID (name)", value=id_string, inline=True) 
            embed.add_field(name="Added (age)", value=add_string, inline=True)
            embed.add_field(name="State", value=state_string, inline=True)
            return embed
        
        def get_pretty_string(self, id):
            member = self.member_list[id]
            string = f'Name: {member.name}\n'
            string += f'Add Time: {member.add_time.strftime("%Y%m%d|%H:%M:%S")}\n'
            string += f'Warn Time: {member.warn_time.strftime("%Y%m%d|%H:%M:%S")}\n'
            string += f'Kick Time: {member.kick_time.strftime("%Y%m%d|%H:%M:%S")}\n'
            if(member.trim_retention_time is None):
                string += f'Retention Time: None\n'
            else:
                string += f'Retention Time: {member.trim_retention_time.strftime("%Y%m%d|%H:%M:%S")}\n'
            string += f'State: {member.state.name}'
            return string

        def get_ids(self):
            return self.member_list.keys()

        def get_member(self, id):
            return self.member_list[id]

    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.guild = int(os.getenv('PESUKARHU_GUILD'))
        self.admin_role_id = int(os.getenv('PESUKARHU_ADMIN_ROLE'))
        self.refresh_period = float(os.getenv('PESUKARHU_MEMBER_REFRESH_PERIOD'))
        self.verified_role_id = int(os.getenv('PESUKARHU_VERIFIED_ROLE_ID'))
        self.unverified_role_id = int(os.getenv('PESUKARHU_UNVERIFIED_ROLE_ID'))
        self.unverified_warning_role_id = int(os.getenv('PESUKARHU_WARNING_ROLE_ID'))
        self.warnings_channel = int(os.getenv('PESUKARHU_WARNING_CHANNEL'))
        self.log_channel = int(os.getenv('PESUKARHU_LOG_CHANNEL'))
        self.raid_detection_window = float(os.getenv('PESUKARHU_RAID_DETECTION_WINDOW'))
        self.raid_detection_level = int(os.getenv('PESUKARHU_RAID_DETECTION_LEVEL'))
        logging.info(f'Initializing MemberMonitor:')
        logging.info(f'   guild = {self.guild}')
        logging.info(f'   admin role id = {self.admin_role_id}')
        logging.info(f'   refresh period = {self.refresh_period}')
        logging.info(f'   verified role id = {self.verified_role_id}')
        logging.info(f'   unverified role id = {self.unverified_role_id}')
        logging.info(f'   unverified warning role id = {self.unverified_warning_role_id}')
        logging.info(f'   warnings channel = {self.warnings_channel}')
        logging.info(f'   log channel = {self.log_channel}')
        logging.info(f'   raid detection window = {self.raid_detection_window}')
        logging.info(f'   raid detection level = {self.raid_detection_level}')
        # Initialize member list maintenance search task
        self.member_list = self.MemberList()
        self.member_list_maintenance.change_interval(seconds = self.refresh_period)
        self.member_list_maintenance.start()
        # Setup some random color constants
        self.red = 0xFF4500
        self.green = 0x32CD32
        self.yellow = 0xFFFF00

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.member_list.add_member(member.id, member.name)
        # Advertise joining
        channel = self.bot.get_channel(self.log_channel)
        if channel is not None:
            embed=discord.Embed(color=self.yellow)
            embed.add_field(name="Mention (ID)", value=f'<@{member.id}> ({member.id})', inline=True) 
            embed.add_field(name="Name", value=f'{member.name}', inline=True)
            embed.add_field(name="Nick", value=f'{member.nick}', inline=True)
            embed.set_author(name=f'{member.name} joined server', icon_url=member.avatar_url)
            await channel.send(embed=embed)
        # Check if this overflows raid detector
        raid_count = self.member_list.count_recent_joins(self.raid_detection_window)
        if(raid_count >= self.raid_detection_level):
            logging.warning(f'Raid detected - {raid_count} members joined inside window of {self.raid_detection_window} (max of {self.raid_detection_level} allowed)')
            channel = self.bot.get_channel(self.log_channel)
            if channel is not None:
                guild = self.bot.get_guild(self.guild)
                admin_role = guild.get_role(self.admin_role_id)
                embed=discord.Embed(color=self.red, description=f'Raid detected - {admin_role.mention}')
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        logging.info(f'{member.id} | {member.name} left server')
        self.member_list.set_removed_state(member.id)
        channel = self.bot.get_channel(self.log_channel)
        if channel is not None:
            embed=discord.Embed(color=self.red)
            embed.add_field(name="Mention (ID)", value=f'<@{member.id}> ({member.id})', inline=True) 
            embed.add_field(name="Name", value=f'{member.name}', inline=True)
            embed.add_field(name="Nick", value=f'{member.nick}', inline=True)
            embed.set_author(name=f'{member.name} left server', icon_url=member.avatar_url)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Gain Unverified ==> do nothing (could add, but on_member_join does same thing)
        # Gain Verified ==> remove from member list
        # Lose Verified ==> add to member list (mostly just for test)
        was_verified = discord.utils.find(lambda r: r.id == self.verified_role_id, before.roles)
        is_verified = discord.utils.find(lambda r: r.id == self.verified_role_id, after.roles)
        was_unverified = discord.utils.find(lambda r: r.id == self.unverified_role_id, before.roles)
        is_unverified = discord.utils.find(lambda r: r.id == self.unverified_role_id, after.roles)
        if is_verified is not None and was_verified is None:
            self.member_list.verify_member(after.id)
            channel = self.bot.get_channel(self.log_channel)
            if channel is not None:
                embed=discord.Embed(color=self.green)
                embed.add_field(name="Mention (ID)", value=f'<@{after.id}> ({after.id})', inline=True) 
                embed.add_field(name="Name", value=f'{after.name}', inline=True)
                embed.add_field(name="Nick", value=f'{after.nick}', inline=True)
                embed.set_author(name=f'{after.name} was verified', icon_url=after.avatar_url)
                await channel.send(embed=embed)
            # Remove warning role, if appropriate
            guild = self.bot.get_guild(self.guild)
            warning_role = guild.get_role(self.unverified_warning_role_id)
            warned_member = guild.get_member(after.id)
            await warned_member.remove_roles(warning_role,
                                             reason=f'User completed verification')
        if is_unverified is not None and was_unverified is None:
            self.member_list.unverify_member(after.id, after.name)

    @commands.command()
    async def member_list(self, ctx):
        await ctx.send(embed=self.member_list.get_embed())

    @commands.command()
    async def ban_time(self, ctx, start_time_ago, end_time_ago):
        logging.warning(f'Ban Time Command String: {ctx.message.content}')
        logging.warning(f'Ban Time Actor: {ctx.message.author.id} | {ctx.message.author.name}')
        start_time_ago = pytimeparse.timeparse.timeparse(start_time_ago)
        end_time_ago = pytimeparse.timeparse.timeparse(end_time_ago)
        logging.warning(f'Ban Arguments: {start_time_ago} (s) ago to {end_time_ago} (s) ago')
        if(start_time_ago < end_time_ago):
            await ctx.send(f'Banning all joins from {start_time_ago} (s) to {end_time_ago} (s) ago')
            current_time = datetime.datetime.now()
            ids = self.member_list.get_ids()
            for id in ids:
                member = self.member_list.get_member(id)
                age = current_time - member.add_time
                age = age.total_seconds()
                if((age > start_time_ago) and (age < end_time_ago)):
                    await ctx.send(f'Banning {id} | {member.name}')
                    guild = self.bot.get_guild(self.guild)
                    banned_member = guild.get_member(id)
                    logging.info(f'Banned {id} | {member.name} for verification')
                    await banned_member.create_dm()
                    await banned_member.dm_channel.send(
                        f'{member.name} - you were banned from the Personal Finance Discord due to a raid by spammer bots.\n' \
                        f'If this was in error and you are a real person, email lufisraccoon@gmail.com or metacognition@gmail.com\n' \
                        f'Please provide this information to them:\n' \
                        f'ID: {id} | Name: {member.name} | Date: {current_time}'
                    )
                    await guild.ban(banned_member,
                                    reason=f'Banned member due to $ban_time command by {ctx.message.author.name}')
        else:
            await ctx.send(f'End time is before start time. Order is start end - ie, banning from 30s ago to 60s ago would be $ban_time 30s 60s')

    @tasks.loop(seconds=10) # default value is overridden prior to execution
    async def member_list_maintenance(self):
        # Maintain list
        self.member_list.trim_unmonitored_members();
        # Check for people who have been on unverified list too long.
        current_time = datetime.datetime.now()
        ids = self.member_list.get_ids()
        for id in ids:
            member = self.member_list.get_member(id)
            if((member.state == MemberMonitor.MemberState.UNVERIFIED) and (member.warn_time) < current_time):
                guild = self.bot.get_guild(self.guild)
                warned_member = guild.get_member(id)
                await warned_member.create_dm()
                await warned_member.dm_channel.send(
                    f'{member.name} - you will be kicked from the Personal Finance Discord if you do not complete the verification process.\n' \
                    f'We do this to ensure that our users are humans and not advertising bots.\n' \
                    f'Please see #verify-step-1 and #verify-step-2 to see what you need to do for verification\n'
                )
                warning_role = guild.get_role(self.unverified_warning_role_id)
                await warned_member.add_roles(warning_role,
                                              reason=f'Warned for verification - joined at {member.add_time}, current time is {current_time}')
                logging.info(f'Warned {id} | {member.name} for verification')
                channel = self.bot.get_channel(self.warnings_channel)
                await channel.send(f'<@{id}> - please complete the verification process - see your DMs for additional info')
                self.member_list.warn_member(id)
                continue
            if((member.state == MemberMonitor.MemberState.WARNED) and (member.kick_time < current_time)):
                guild = self.bot.get_guild(self.guild)
                kicked_member = guild.get_member(id)
                logging.info(f'Kicked warned {id} | {member.name} for verification')
                await kicked_member.create_dm()
                await kicked_member.dm_channel.send(
                    f'{member.name} - you were kicked from the Personal Finance Discord due to lack of verification.\n' \
                    f'We do this to ensure that our users are humans and not advertising bots.\n' \
                    f'If this was in error, you are free to re-join the server at any time through this invite URL:' \
                    f'http://discord.gg/agSSAhXzYD'
                )
                await guild.kick(kicked_member,
                                 reason=f'Kicked for failed verification - joined at {member.add_time}, current time is {current_time}')
                channel = self.bot.get_channel(self.log_channel)
                await channel.send(f'<@{id}> was kicked due to lack of verification')
                # Don't need to remove member, is already done in on_member_remove + trim functions
                continue

    @member_list_maintenance.before_loop
    async def before_member_list_maintenance(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(self.guild)
        logging.info(f'{self.bot.user} is connected to {guild.name} (id: {guild.id})')
        # Add all users with Unverified role to our list; we'll add more as we go
        for member in guild.members:
            for role in member.roles: 
                if role.id == self.unverified_role_id:
                    logging.info(f'Found pre-existing unverified member: {guild.id} | {member.name}')
                    self.member_list.add_member(member.id, member.name)
                if role.id == self.unverified_warning_role_id:
                    logging.info(f'Found pre-existing warned member: {guild.id} | {member.name}')
                    self.member_list.add_member(member.id, member.name)
                    self.member_list.warn_member(member.id)

    async def cog_check(self, ctx):
        # Check if user has admin role
        guild = self.bot.get_guild(self.guild)
        admin_role = guild.get_role(self.admin_role_id)
        return admin_role in ctx.author.roles

    @commands.Cog.listener()
    async def on_message(self, message):
        if("raccoon" in message.content.lower()):
            await message.add_reaction("🦝")