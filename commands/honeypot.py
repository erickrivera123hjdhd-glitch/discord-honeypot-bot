import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

class HoneypotView(discord.ui.View):
    def __init__(self, bot, database, guild_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.database = database
        self.guild_id = guild_id
        self._update_buttons()
    
    def _update_buttons(self):
        self.clear_items()
        honeypot_data = self.database.get_honeypot_channel(self.guild_id)
        enabled = honeypot_data and honeypot_data.get('enabled', False)
        channel_id = honeypot_data['channel_id'] if honeypot_data else None
        
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.success if not enabled else discord.ButtonStyle.danger,
            label='Enable Honeypot' if not enabled else 'Disable Honeypot',
            custom_id='toggle_honeypot'
        ))
        
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label='Configure Channel',
            custom_id='configure_channel'
        ))
        
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label='View Channels',
            custom_id='view_channels'
        ))
        
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label='View Recent Triggers',
            custom_id='view_triggers'
        ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Only administrators can use this panel.', ephemeral=True)
            return False
        return True
    
    @discord.ui.button(style=discord.ButtonStyle.success, label='Enable Honeypot', custom_id='toggle_honeypot')
    async def toggle_honeypot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Only administrators can use this panel.', ephemeral=True)
            return
        
        honeypot_data = self.database.get_honeypot_channel(self.guild_id)
        enabled = honeypot_data and honeypot_data.get('enabled', False)
        
        if enabled:
            self.database.disable_honeypot(self.guild_id)
            await interaction.response.send_message('Honeypot disabled.', ephemeral=True)
        else:
            if honeypot_data:
                await interaction.response.send_message('Please configure a channel first using /honeypot configure.', ephemeral=True)
            else:
                await interaction.response.send_message('No honeypot channel configured. Use /honeypot configure first.', ephemeral=True)
        
        self._update_buttons()
        await interaction.message.edit(view=self)
    
    @discord.ui.button(style=discord.ButtonStyle.primary, label='Configure Channel', custom_id='configure_channel')
    async def configure_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Only administrators can use this panel.', ephemeral=True)
            return
        
        await interaction.response.send_message(
            'Please select a channel to configure as honeypot:',
            view=ChannelSelectView(self.bot, self.database, self.guild_id, interaction.user)
        )
    
    @discord.ui.button(style=discord.ButtonStyle.secondary, label='View Channels', custom_id='view_channels')
    async def view_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Only administrators can use this panel.', ephemeral=True)
            return
        
        honeypot_data = self.database.get_honeypot_channel(self.guild_id)
        if honeypot_data and honeypot_data.get('enabled'):
            channel = interaction.guild.get_channel(honeypot_data['channel_id'])
            embed = discord.Embed(title='Honeypot Channel', color=discord.Color.green())
            embed.add_field(name='Channel', value=channel.mention if channel else 'Unknown', inline=False)
            embed.add_field(name='Status', value='Enabled', inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message('No honeypot channel is currently enabled.', ephemeral=True)
    
    @discord.ui.button(style=discord.ButtonStyle.secondary, label='View Recent Triggers', custom_id='view_triggers')
    async def view_triggers(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Only administrators can use this panel.', ephemeral=True)
            return
        
        triggers = self.database.get_recent_triggers(self.guild_id, limit=10)
        if not triggers:
            await interaction.response.send_message('No recent triggers.', ephemeral=True)
            return
        
        embed = discord.Embed(title='Recent Triggers', color=discord.Color.red())
        for t in triggers:
            channel = interaction.guild.get_channel(t['channel_id'])
            channel_name = channel.name if channel else 'Unknown'
            embed.add_field(
                name=f"{t['username']} (ID: {t['user_id']})",
                value=f"Channel: {channel_name} | Type: {t['attachment_type']} | {t['timestamp']}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)\n
class ChannelSelectView(discord.ui.View):
    def __init__(self, bot, database, guild_id: int, user: discord.User):
        super().__init__(timeout=60)
        self.bot = bot
        self.database = database
        self.guild_id = guild_id
        self.user = user
    
    @discord.ui.channel_select(
        placeholder='Select a honeypot channel...',
        channel_types=[discord.ChannelType.text, discord.ChannelType.forum],
        max_values=1
    )
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Only administrators can use this panel.', ephemeral=True)
            return
        
        channel = select.values[0]
        self.database.set_honeypot_channel(guild_id=self.guild_id, channel_id=channel.id, enabled=True)
        
        await interaction.response.send_message(
            f'Honeypot channel set to {channel.mention}!',
            ephemeral=True
        )
        
        await self._send_warning_message(channel)
        
        view = HoneypotView(self.bot, self.database, self.guild_id)
        await interaction.followup.send(
            'Honeypot Configuration Panel',
            view=view,
            ephemeral=True
        )
    
    async def _send_warning_message(self, channel: discord.abc.Messageable):
        try:
            await channel.send(
                "⚠️ DO NOT POST IMAGES OR FILES IN THIS CHANNEL.\n"
                "Posting an image or file will result in an automatic kick."
            )
        except discord.Forbidden:
            pass

class HoneypotCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
    
    @app_commands.command(name='honeypot', description='Open the honeypot configuration panel')
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot(self, interaction: discord.Interaction):
        view = HoneypotView(self.bot, self.database, interaction.guild_id)
        await interaction.response.send_message('Honeypot Configuration Panel', view=view, ephemeral=True)
    
    @app_commands.command(name='honeypot_configure', description='Configure honeypot channel')
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot_configure(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.database.set_honeypot_channel(guild_id=interaction.guild_id, channel_id=channel.id, enabled=True)
        await channel.send(
            "⚠️ DO NOT POST IMAGES OR FILES IN THIS CHANNEL.\n"
            "Posting an image or file will result in an automatic kick."
        )
        await interaction.response.send_message(f'Honeypot channel set to {channel.mention}!', ephemeral=True)
    
    @app_commands.command(name='honeypot_disable', description='Disable honeypot')
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot_disable(self, interaction: discord.Interaction):
        self.database.disable_honeypot(interaction.guild_id)
        await interaction.response.send_message('Honeypot disabled.', ephemeral=True)
    
    @app_commands.command(name='honeypot_status', description='View honeypot status')
    async def honeypot_status(self, interaction: discord.Interaction):
        honeypot_data = self.database.get_honeypot_channel(interaction.guild_id)
        if honeypot_data and honeypot_data.get('enabled'):
            channel = interaction.guild.get_channel(honeypot_data['channel_id'])
            embed = discord.Embed(title='Honeypot Status', color=discord.Color.green())
            embed.add_field(name='Channel', value=channel.mention if channel else 'Unknown', inline=False)
            embed.add_field(name='Status', value='Enabled', inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message('Honeypot is not configured or disabled.', ephemeral=True)
    
    @app_commands.command(name='honeypot_exempt', description='Add exemption for user or role')
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot_exempt(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member = None,
        role: discord.Role = None,
        exempt_bots: bool = False
    ):
        if not user and not role:
            await interaction.response.send_message('Please provide either a user or a role to exempt.', ephemeral=True)
            return
        
        if user:
            self.database.add_exemption(interaction.guild_id, user_id=user.id, exempt_bots=exempt_bots)
            await interaction.response.send_message(f'User {user.mention} has been exempted.', ephemeral=True)
        elif role:
            self.database.add_exemption(interaction.guild_id, role_id=role.id, exempt_bots=exempt_bots)
            await interaction.response.send_message(f'Role {role.name} has been exempted.', ephemeral=True)
    
    @app_commands.command(name='honeypot_exemptions', description='View all exemptions')
    async def honeypot_exemptions(self, interaction: discord.Interaction):
        exemptions = self.database.get_exemptions(interaction.guild_id)
        if not exemptions:
            await interaction.response.send_message('No exemptions configured.', ephemeral=True)
            return
        
        embed = discord.Embed(title='Honeypot Exemptions', color=discord.Color.blue())
        for ex in exemptions:
            if ex['user_id']:
                member = interaction.guild.get_member(ex['user_id'])
                if member:
                    embed.add_field(name='User', value=f"{member.mention} (Bot: {member.bot})", inline=False)
            if ex['role_id']:
                role = interaction.guild.get_role(ex['role_id'])
                if role:
                    embed.add_field(name='Role', value=role.name, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name='honeypot_triggers', description='View recent triggers')
    async def honeypot_triggers(self, interaction: discord.Interaction, limit: int = 10):
        triggers = self.database.get_recent_triggers(interaction.guild_id, limit=limit)
        if not triggers:
            await interaction.response.send_message('No recent triggers.', ephemeral=True)
            return
        
        embed = discord.Embed(title='Recent Triggers', color=discord.Color.red())
        for t in triggers:
            channel = interaction.guild.get_channel(t['channel_id'])
            channel_name = channel.name if channel else 'Unknown'
            embed.add_field(
                name=f"{t['username']} (ID: {t['user_id']})",
                value=f"Channel: {channel_name} | Type: {t['attachment_type']} | {t['timestamp']}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

from database import Database