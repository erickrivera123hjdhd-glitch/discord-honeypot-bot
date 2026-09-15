import discord
from discord.ext import commands
from database import Database
from typing import Optional

class MessageCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if not message.attachments:
            return
        
        if not message.guild:
            return
        
        honeypot_data = self.database.get_honeypot_channel(message.guild.id)
        if not honeypot_data or not honeypot_data.get('enabled'):
            return
        
        if message.channel.id != honeypot_data['channel_id']:
            return
        
        if self.database.is_exempt(message.guild.id, message.author.id, [role.id for role in message.author.roles], message.author.bot):
            return
        
        await self._handle_attachment(message)
    
    async def _handle_attachment(self, message: discord.Message):
        if not message.channel.permissions_for(message.author).send_messages:
            return
        
        bot_permissions = message.channel.permissions_for(message.guild.me)
        if not bot_permissions.manage_messages or not bot_permissions.kick_members:
            return
        
        attachment = message.attachments[0]
        attachment_type = self._get_attachment_type(attachment)
        
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        
        try:
            await message.author.kick(reason=f'Posted {attachment_type} in honeypot channel')
        except discord.Forbidden:
            return
        except discord.HTTPException:
            return
        
        self.database.log_trigger(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            user_id=message.author.id,
            username=str(message.author),
            attachment_type=attachment_type,
            message_id=message.id
        )
        
        await self._send_mod_log(message, attachment_type)
    
    def _get_attachment_type(self, attachment: discord.Attachment) -> str:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            return 'image'
        return 'file'
    
    async def _send_mod_log(self, message: discord.Message, attachment_type: str):
        guild = message.guild
        honeypot_data = self.database.get_honeypot_channel(guild.id)
        channel = guild.get_channel(honeypot_data['channel_id']) if honeypot_data else None
        
        embed = discord.Embed(
            title='Honeypot Trigger',
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name='User', value=f"{message.author} (ID: {message.author.id})", inline=False)
        embed.add_field(name='Attachment Type', value=attachment_type, inline=False)
        embed.add_field(name='Channel', value=channel.mention if channel else 'Unknown', inline=False)
        embed.set_footer(text='User has been kicked from the server')
        
        system_channel = guild.system_channel
        if system_channel and system_channel.permissions_for(guild.me).send_messages:
            try:
                await system_channel.send(embed=embed)
            except discord.Forbidden:
                pass