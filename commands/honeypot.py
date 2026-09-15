import discord
from discord import app_commands
from discord.ext import commands


WARNING_MESSAGE = (
    "⚠️ DO NOT POST IMAGES OR FILES IN THIS CHANNEL.\n"
    "Posting an image or file will result in an automatic kick."
)


class HoneypotView(discord.ui.View):
    def __init__(self, bot, database, guild_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.database = database
        self.guild_id = guild_id

        self.toggle_button = discord.ui.Button(
            custom_id="honeypot_toggle",
            label="Enable Honeypot",
            style=discord.ButtonStyle.success,
        )
        self.configure_button = discord.ui.Button(
            custom_id="honeypot_configure",
            label="Configure Channel",
            style=discord.ButtonStyle.primary,
        )
        self.channels_button = discord.ui.Button(
            custom_id="honeypot_channels",
            label="View Channel",
            style=discord.ButtonStyle.secondary,
        )
        self.triggers_button = discord.ui.Button(
            custom_id="honeypot_triggers",
            label="Recent Triggers",
            style=discord.ButtonStyle.secondary,
        )

        self.toggle_button.callback = self.toggle_honeypot
        self.configure_button.callback = self.configure_channel
        self.channels_button.callback = self.view_channels
        self.triggers_button.callback = self.view_triggers

        self.add_item(self.toggle_button)
        self.add_item(self.configure_button)
        self.add_item(self.channels_button)
        self.add_item(self.triggers_button)
        self._update_buttons()

    def _update_buttons(self):
        data = self.database.get_honeypot_channel(self.guild_id)
        enabled = bool(data and data.get("enabled"))
        configured = bool(data and data.get("channel_id"))

        self.toggle_button.label = "Disable Honeypot" if enabled else "Enable Honeypot"
        self.toggle_button.style = discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success
        self.toggle_button.disabled = not configured
        self.configure_button.label = "Change Channel" if configured else "Configure Channel"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Only server administrators can use this panel.", ephemeral=True
                )
            return False
        return True

    async def toggle_honeypot(self, interaction: discord.Interaction):
        data = self.database.get_honeypot_channel(self.guild_id)
        if not data:
            await interaction.response.send_message(
                "No honeypot channel is configured yet. Click Configure Channel first.",
                ephemeral=True,
            )
            return

        if data.get("enabled"):
            self.database.disable_honeypot(self.guild_id)
            message = "🔴 Honeypot disabled."
        else:
            self.database.set_honeypot_channel(
                guild_id=self.guild_id,
                channel_id=data["channel_id"],
                enabled=True,
            )
            message = "🟢 Honeypot enabled."

        self._update_buttons()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(message, ephemeral=True)

    async def configure_channel(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Select the channel you want to use as the honeypot:",
            view=ChannelSelectView(self.bot, self.database, self.guild_id, interaction.user),
            ephemeral=True,
        )

    async def view_channels(self, interaction: discord.Interaction):
        data = self.database.get_honeypot_channel(self.guild_id)
        if not data:
            await interaction.response.send_message(
                "No honeypot channel is configured.", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(data["channel_id"])
        status = "Enabled" if data.get("enabled") else "Disabled"
        embed = discord.Embed(title="Honeypot Channel", color=discord.Color.green())
        embed.add_field(
            name="Channel",
            value=channel.mention if channel else "Unknown / deleted",
            inline=False,
        )
        embed.add_field(name="Status", value=status, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def view_triggers(self, interaction: discord.Interaction):
        triggers = self.database.get_recent_triggers(self.guild_id, limit=10)
        if not triggers:
            await interaction.response.send_message(
                "No recent honeypot triggers.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Recent Honeypot Triggers", color=discord.Color.red())
        for trigger in triggers:
            channel = interaction.guild.get_channel(trigger["channel_id"])
            channel_name = channel.name if channel else "Unknown"
            embed.add_field(
                name=f'{trigger["username"]} (ID: {trigger["user_id"]})',
                value=(
                    f'Channel: {channel_name}\n'
                    f'Type: {trigger["attachment_type"]}\n'
                    f'Time: {trigger["timestamp"]}'
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ChannelSelectView(discord.ui.View):
    def __init__(self, bot, database, guild_id: int, user: discord.User):
        super().__init__(timeout=60)
        self.bot = bot
        self.database = database
        self.guild_id = guild_id
        self.user = user

        self.select = discord.ui.ChannelSelect(
            placeholder="Select a honeypot channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )
        self.select.callback = self.select_channel
        self.add_item(self.select)

    async def select_channel(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only the administrator who opened this selector can use it.",
                ephemeral=True,
            )
            return

        selected = self.select.values[0]
        channel_id = getattr(selected, "id", None)
        guild = interaction.guild
        channel = guild.get_channel(channel_id) if guild and channel_id else None

        if channel is None:
            await interaction.response.send_message(
                "I couldn't resolve that channel. Please try again.", ephemeral=True
            )
            return

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Please select a normal text channel.", ephemeral=True
            )
            return

        bot_member = guild.me
        if bot_member is None:
            await interaction.response.send_message(
                "I couldn't verify my server permissions. Please try again.", ephemeral=True
            )
            return

        permissions = channel.permissions_for(bot_member)
        if not permissions.view_channel or not permissions.send_messages:
            await interaction.response.send_message(
                "I need View Channel and Send Messages permissions in that channel.",
                ephemeral=True,
            )
            return

        if not permissions.manage_messages or not permissions.kick_members:
            await interaction.response.send_message(
                "I also need Manage Messages and Kick Members permissions for the honeypot to work.",
                ephemeral=True,
            )
            return

        self.database.set_honeypot_channel(
            guild_id=self.guild_id,
            channel_id=channel.id,
            enabled=True,
        )

        await interaction.response.send_message(
            f"🟢 Honeypot channel set to {channel.mention}!",
            ephemeral=True,
        )
        await self._send_warning_message(channel)
        self.stop()

    async def _send_warning_message(self, channel: discord.TextChannel):
        try:
            await channel.send(WARNING_MESSAGE)
        except (discord.Forbidden, discord.HTTPException):
            pass


class HoneypotCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database):
        self.bot = bot
        self.database = database

    @app_commands.command(name="honeypot", description="Open the honeypot configuration panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot(self, interaction: discord.Interaction):
        view = HoneypotView(self.bot, self.database, interaction.guild_id)
        await interaction.response.send_message(
            "🍯 **Honeypot Configuration**\nUse the buttons below to manage your honeypot.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="honeypot_configure", description="Configure honeypot channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot_configure(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.database.set_honeypot_channel(
            guild_id=interaction.guild_id,
            channel_id=channel.id,
            enabled=True,
        )
        await self._warn_channel(channel)
        await interaction.response.send_message(
            f"🟢 Honeypot channel set to {channel.mention}!",
            ephemeral=True,
        )

    async def _warn_channel(self, channel: discord.TextChannel):
        try:
            await channel.send(WARNING_MESSAGE)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @app_commands.command(name="honeypot_disable", description="Disable honeypot")
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot_disable(self, interaction: discord.Interaction):
        self.database.disable_honeypot(interaction.guild_id)
        await interaction.response.send_message("🔴 Honeypot disabled.", ephemeral=True)

    @app_commands.command(name="honeypot_status", description="View honeypot status")
    async def honeypot_status(self, interaction: discord.Interaction):
        data = self.database.get_honeypot_channel(interaction.guild_id)
        if data and data.get("enabled"):
            channel = interaction.guild.get_channel(data["channel_id"])
            embed = discord.Embed(title="Honeypot Status", color=discord.Color.green())
            embed.add_field(name="Channel", value=channel.mention if channel else "Unknown", inline=False)
            embed.add_field(name="Status", value="Enabled", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "Honeypot is not configured or disabled.", ephemeral=True
            )

    @app_commands.command(name="honeypot_exempt", description="Add exemption for user or role")
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot_exempt(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        role: discord.Role = None,
        exempt_bots: bool = False,
    ):
        if not user and not role:
            await interaction.response.send_message(
                "Please provide either a user or a role to exempt.", ephemeral=True
            )
            return

        if user:
            self.database.add_exemption(interaction.guild_id, user_id=user.id, exempt_bots=exempt_bots)
            await interaction.response.send_message(
                f"User {user.mention} has been exempted.", ephemeral=True
            )
        else:
            self.database.add_exemption(interaction.guild_id, role_id=role.id, exempt_bots=exempt_bots)
            await interaction.response.send_message(
                f"Role {role.name} has been exempted.", ephemeral=True
            )

    @app_commands.command(name="honeypot_exemptions", description="View all exemptions")
    async def honeypot_exemptions(self, interaction: discord.Interaction):
        exemptions = self.database.get_exemptions(interaction.guild_id)
        if not exemptions:
            await interaction.response.send_message("No exemptions configured.", ephemeral=True)
            return

        embed = discord.Embed(title="Honeypot Exemptions", color=discord.Color.blue())
        for exemption in exemptions:
            if exemption["user_id"]:
                member = interaction.guild.get_member(exemption["user_id"])
                if member:
                    embed.add_field(
                        name="User",
                        value=f"{member.mention} (Bot: {member.bot})",
                        inline=False,
                    )
            if exemption["role_id"]:
                role = interaction.guild.get_role(exemption["role_id"])
                if role:
                    embed.add_field(name="Role", value=role.name, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="honeypot_triggers", description="View recent triggers")
    async def honeypot_triggers(self, interaction: discord.Interaction, limit: int = 10):
        limit = max(1, min(limit, 25))
        triggers = self.database.get_recent_triggers(interaction.guild_id, limit=limit)
        if not triggers:
            await interaction.response.send_message("No recent triggers.", ephemeral=True)
            return

        embed = discord.Embed(title="Recent Triggers", color=discord.Color.red())
        for trigger in triggers:
            channel = interaction.guild.get_channel(trigger["channel_id"])
            channel_name = channel.name if channel else "Unknown"
            embed.add_field(
                name=f'{trigger["username"]} (ID: {trigger["user_id"]})',
                value=f'Channel: {channel_name} | Type: {trigger["attachment_type"]} | {trigger["timestamp"]}',
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)
