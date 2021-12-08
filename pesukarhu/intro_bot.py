import os
import re
import discord
import datetime
from discord.ext import commands
from discord.ext.commands import bot
from dotenv import load_dotenv
import logging
import yaml

class IntroBot(commands.Cog):
    class State():
        '''
        Stores state of the bot / reads/retrieves from state file
        ''' 
        def __init__(self, state_file):
            with open("intro_bot_state.yaml", 'r') as stream:
                config = yaml.safe_load(stream)

            self.ticket_count = int(config['ticket_count'])
            self.intro_id = int(config['intro_id'])

        def store(self):
            config = {}
            config['ticket_count'] = self.ticket_count
            config['intro_id'] = self.intro_id

            with open("intro_bot_state.yaml", 'w') as stream:
                yaml.dump(config, stream)

    class Settings():
        '''
        Stores settings of the bot
        '''
        def __init__(self, state_file):
            with open("intro_bot_settings.yaml", 'r') as stream:
                config = yaml.safe_load(stream)

            self.guild = int(config['guild'])
            self.log_channel = int(config['log_channel'])
            self.warning_channel = int(config['warning_channel'])
            self.verifier_role = int(config['verifier_role'])
            self.prefix = config['prefix']
            self.questions = config['questions']
            self.intro_message_title = config['intro_message_title']
            self.intro_message_description = config['intro_message_description']
            self.timeout_offset = datetime.timedelta(0, config['timeout_offset'])

    class Question():
        '''
        Stores info a single question asked
        '''
        def __init__(self, question):
            current_time = datetime.datetime.now()
            self.question = question
            self.response = ""
            self.time_asked = current_time
            self.time_responded = None

    class Member():
        '''
        Stores information about a user ID
        '''
        def __init__(self, name, channel, timeout_offset):
            current_time = datetime.datetime.now()
            self.name = name
            self.channel = channel
            self.questions = []
            self.add_time = current_time
            self.timeout = current_time + timeout_offset
        
        def add_question(self, question):
            self.questions.append(question)

        def get_current_question_index(self):
            return len(self.questions)

        def record_response(self, response):
            current_time = datetime.datetime.now()
            question_idx = self.get_current_question_index()
            self.questions[question_idx-1].response = response
            self.questions[question_idx-1].time_responded = current_time

    class Log():
        '''
        Stores information about all user ID being verified, indexed by ID
        '''
        def __init__(self, bot, settings):
            self.bot = bot
            self.settings = settings
            self.log = {}
        
        def add_user(self, id, name, channel):
            logging.info(f'Adding user: {id} - {name} - channel: {channel}')
            self.log[id] = IntroBot.Member(name, channel, self.settings.timeout_offset)

        def add_question(self, id, question):
            self.log[id].add_question(IntroBot.Question(question))

        def get_current_question_index(self, id):
            return self.log[id].get_current_question_index()

        def record_response(self, id, response):
            self.log[id].record_response(response)

        def remove_user(self, id):
            logging.info(f'Removing user: {id}')
            del self.log[id]

        def get_member(self, id):
            return self.log[id]

        def get_embed(self):
            current_time = datetime.datetime.now()

            if(len(self.log) == 0):
                id_string = "Empty"
                channel_string = "Empty"
                age_string = "Empty"
            else:
                id_string = ""
                channel_string = ""
                age_string = ""

                guild = self.bot.get_guild(self.settings.guild)

                for key, member in self.log.items():
                    age = current_time - member.add_time # as timedelta object
                    age = age.total_seconds() # as float

                    new_id = f'<@{key}>\n'
                    ticket_channel = guild.get_channel(member.channel)
                    new_channel = f'{ticket_channel.mention} ({member.get_current_question_index()})\n'
                    new_age = f'{member.add_time.strftime("%Y%m%d|%H:%M:%S")} ({age:.0f})\n'
                    # Check to make sure we don't exceed 1024 characters per field. We
                    # won't hit the 6000 character total limit
                    if((len(id_string) + len(new_id) <= 1000) and \
                       (len(channel_string) + len(new_channel) <= 1000) and \
                       (len(age_string) + len(new_age) <= 1000)):
                        id_string += new_id
                        channel_string += new_channel
                        age_string += new_age
                    else:
                        break

            embed=discord.Embed(title=f'Verification list: ({len(self.log)} members)')
            embed.add_field(name="Name", value=id_string, inline=True) 
            embed.add_field(name="Progress", value=channel_string, inline=True)
            embed.add_field(name="Age", value=age_string, inline=True)

            return embed

    def __init__(self, bot):
        self.bot = bot
        self.settings = self.Settings('intro_bot_settings.yaml')
        self.log = self.Log(bot, self.settings)
        self.state = self.State('intro_bot_state.yaml')
        logging.info(f'Initializing IntroBot:')
        logging.info(f'   prefix = "{self.settings.prefix}"')
        for question in self.settings.questions:
            logging.info(f'   question = "{question}"')
        # Setup some random color constants
        self.red = 0xFF4500
        self.green = 0x32CD32
        self.yellow = 0xFFFF00

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info(f'{self.bot.user} is enabled')

    @commands.command()
    async def create_intro(self, ctx):
        embed = (discord.Embed(title=self.settings.intro_message_title, description=self.settings.intro_message_description)
                        .set_footer(text=f'Made by {ctx.author.display_name}'))

        message = await ctx.send(embed=embed)
        self.state.intro_id = message.id
        emojis = ['🚫', '✅', '⛔']
        for emoji in emojis:
            await message.add_reaction(emoji)

        logging.info(f'{ctx.author.display_name} created intro - message ID is {message.id}')

    @commands.command()
    async def set_intro_id(self, ctx, intro_id):
        # Should use a converter here with an exception, but I can't figure out how to make the converters work
        if(str.isdigit(intro_id)):
            self.state.intro_id = int(intro_id)
        else:
            logging.info(f'{ctx.author.display_name} attempted to set intro ID with message {ctx.message.content}')
            await ctx.send(f'Huh? {intro_id} is not a number')
            return
        logging.info(f'{ctx.author.display_name} set intro ID to {self.state.intro_id}')
        self.state.store()
        await ctx.send(f'Set intro ID to {self.state.intro_id}')

    async def send_question(self, id, question, ticket_channel):
        question_idx = self.log.get_current_question_index(id)
        self.log.add_question(id, question)
        member = self.log.get_member(id)
        guild = self.bot.get_guild(self.settings.guild)
        channel = guild.get_channel(ticket_channel)
        success = await channel.send(f'<@{id}>: **Question {question_idx+1}**: {question}')
        if success:
            logging.info(f'Sent member {member.name} question {question}')
        else:
            logging.info(f'Failed to send member {member.name} question {question}')

    async def send_next_question(self, id, ticket_channel):
        # Figure out how many questions we've sent them and send the next one
        question_idx = self.log.get_current_question_index(id)
        question = self.settings.questions[question_idx]
        await self.send_question(id, question, ticket_channel)

    @commands.command()
    async def ask_question(self, ctx):
        # Syntax $ask_question <id> question
        message = ctx.message.content
        message = message.split(" ", 2)
        id = message[1]
        question = message[2]
        # Verify second part is a number. Should use a converter here with an exception, but I can't figure out how to make the converters work
        if(str.isdigit(id)):
            id = int(id)
            member = self.log.get_member(id)
            logging.info(f'{ctx.author.display_name} sent additional message to user ID {id} | {member.name}: {ctx.message.content}')
            guild = self.bot.get_guild(self.settings.guild)
            channel = guild.get_channel(member.channel)
            await channel.send('We have an additional clarification question for you.')
            await self.send_question(id, question, member.channel)
        else:
            logging.info(f'{ctx.author.display_name} attempted to send additional question with message {ctx.message.content}')
            await ctx.send(f'Huh? {id} is not a number')
            return

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        member = payload.member
        if member.bot: 
            # don't respond to myself or other bots
            return

        if payload.message_id == self.state.intro_id:
            if payload.emoji.name == '✅':
                logging.info(f'{payload.member.display_name} triggered verification react')
                # Create ticket channel
                guild = self.bot.get_guild(payload.guild_id)
                ticket_channel = await guild.create_text_channel(f'verify-{self.state.ticket_count}')
                await ticket_channel.set_permissions(guild.get_role(guild.id), send_messages=False, read_messages=False)
                await ticket_channel.set_permissions(guild.get_role(self.settings.verifier_role), send_messages=True, read_messages=True, add_reactions=True, embed_links=True, attach_files=True, read_message_history=True, external_emojis=True)
                await ticket_channel.set_permissions(guild.get_member(payload.member.id), send_messages=True, read_messages=True, add_reactions=True, embed_links=True, attach_files=True, read_message_history=True, external_emojis=True)
                self.state.ticket_count += 1
                self.state.store()
                # Add user to log
                self.log.add_user(payload.member.id, payload.member.display_name, ticket_channel.id)
                # Send prefix to channel
                await ticket_channel.send(self.settings.prefix)
                # Send first question in list
                await self.send_next_question(payload.member.id, ticket_channel.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            # don't respond to myself or other bots
            return

        if isinstance(message.channel, discord.channel.TextChannel):
            found = False

            for key, member in self.log.log.items():
                if(message.channel.id == member.channel):
                    found = True
                    break

            if found:
                # Record response
                logging.info(f'{message.author.display_name} sent response: {message.content}')
                self.log.record_response(message.author.id, message.content)
                # Check if we have more to send
                if(self.log.get_current_question_index(message.author.id) >= len(self.settings.questions)):
                    logging.info(f'{message.author.display_name} sent last response!')
                    await message.channel.send('That\'s the last question. Our verification team will either verify your account, ask further question, or deny your application.')
                    # Send responses to log
                    log_channel = self.bot.get_channel(self.settings.log_channel)
                    embed=discord.Embed(color=self.yellow)
                    embed.add_field(name="Mention (ID)", value=f'<@{message.author.id}> ({message.author.id})', inline=True) 
                    embed.add_field(name="Channel", value=f'{message.channel.mention}', inline=True) 
                    for question in self.log.get_member(message.author.id).questions:
                        difference = question.time_responded - question.time_asked
                        time = difference.total_seconds()
                        embed.add_field(name=f'{question.question} (took {time:.0f}s to respond)', value=f'{question.response}', inline=False)
                    embed.set_author(name=f'{message.author.display_name} completed verification questions', icon_url=message.author.avatar_url)
                    await log_channel.send(embed=embed)
                    await log_channel.send(f'**Follow-up options:**')
                    await log_channel.send(f'$approve {message.author.id}')
                    await log_channel.send(f'$ask_question {message.author.id} <question>')
                    await log_channel.send(f'$reject {message.author.id}')
                else:
                    await self.send_next_question(message.author.id, message.channel.id)

    @commands.command()
    async def show_log(self, ctx):
        await ctx.send(embed=self.log.get_embed())
