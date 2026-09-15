import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database import Database
from commands.honeypot import HoneypotCog
from events.message import MessageCog

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_PATH = os.getenv('DB_PATH', 'honeypot.db')

if not BOT_TOKEN:
    raise ValueError('BOT_TOKEN environment variable is required')\n
database = Database(DB_PATH)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def setup_hook():
    await bot.add_cog(HoneypotCog(bot, database))
    await bot.add_cog(MessageCog(bot, database))
    print(f'Logged in as {bot.user}')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Game(name='Honeypot Guardian'))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f'Command error: {error}')

if __name__ == '__main__':
    bot.run(BOT_TOKEN)