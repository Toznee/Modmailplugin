"""
Support Hours Plugin for Modmail
---------------------------------
Sends an automated reply to users when their modmail ticket is opened,
informing them of your support hours.

Install:
    ?plugins add YOUR_GITHUB/YOUR_REPO/support-hours

Config (config.json / ?config set):
    support_hours_message  - Custom message body (optional)
    support_hours_title    - Embed title (optional)
    support_hours_color    - Embed color as hex string, e.g. "FF5733" (optional)
    support_hours_footer   - Embed footer text (optional)
    support_hours_timezone - Timezone label shown in message, e.g. "UTC" (optional)

    If none are set, sensible defaults are used.
"""

from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord.ext import commands

from core import checks
from core.models import PermissionLevel


# ─── Default values (change these to match your server) ───────────────────────

DEFAULT_TITLE = "⏰ Support Hours"

DEFAULT_MESSAGE = (
    "Thanks for reaching out! Our support team will get back to you as soon as possible.\n\n"
    "**Our support hours are:**\n"
    "🕗 Monday – Friday: 9:00 AM – 6:00 PM\n"
    "🕗 Saturday: 10:00 AM – 3:00 PM\n"
    "❌ Sunday: Closed\n\n"
    "If you have contacted us outside of these hours, please be patient and "
    "a staff member will respond when available."
)

DEFAULT_TIMEZONE = "UTC"
DEFAULT_COLOR = 0x2ECC71   # Green
DEFAULT_FOOTER = "We appreciate your patience!"

# ──────────────────────────────────────────────────────────────────────────────


class SupportHours(commands.Cog):
    """Sends support hours to users automatically when a new thread is created."""

    def __init__(self, bot):
        self.bot = bot

    # ── Helper to read config values with fallbacks ──────────────────────────

    def _cfg(self, key: str, fallback):
        """Read a value from Modmail's config, returning `fallback` if not set."""
        value = self.bot.config.get(key)
        if value is None or value == "":
            return fallback
        return value

    def _build_embed(self) -> discord.Embed:
        """Construct the support-hours embed from config or defaults."""
        title = self._cfg("support_hours_title", DEFAULT_TITLE)
        message = self._cfg("support_hours_message", DEFAULT_MESSAGE)
        footer = self._cfg("support_hours_footer", DEFAULT_FOOTER)
        timezone = self._cfg("support_hours_timezone", DEFAULT_TIMEZONE)

        # Color: stored as hex string like "2ECC71", convert to int
        raw_color = self._cfg("support_hours_color", None)
        if raw_color:
            try:
                color = int(str(raw_color).lstrip("#"), 16)
            except ValueError:
                color = DEFAULT_COLOR
        else:
            color = DEFAULT_COLOR

        embed = discord.Embed(
            title=title,
            description=message,
            color=color,
        )
        if footer:
            embed.set_footer(text=f"{footer} • All times {timezone}")

        return embed

    def _is_outside_hours(self) -> bool:
        """Returns True if the current GMT time is between 9:00 PM and 9:00 AM (i.e. outside support hours)."""
        now_hour = datetime.now(timezone.utc).hour  # 0–23 in GMT
        # Outside hours = 21:00 (9pm) through 08:59 (before 9am)
        return now_hour >= 21 or now_hour < 9

    # ── Event: fires when Modmail creates a new thread and it's ready ─────────

    @commands.Cog.listener()
    async def on_thread_ready(self, thread, creator, category, initial_message):
        """
        Called by Modmail when a new thread has been fully set up.
        Only sends the support hours message if the ticket is opened outside
        of support hours (9 PM – 9 AM GMT).
        """
        if not self._is_outside_hours():
            return  # Within support hours — no automated message needed
        embed = self._build_embed()

        try:
            # Send the embed as a bot reply into the thread.
            # This delivers it to the user's DMs just like a normal staff reply.
            await thread.reply(embed=embed)
        except Exception as exc:
            # Log the error but don't crash the bot
            self.bot.logger.error(
                "SupportHours: failed to send support hours message – %s", exc
            )

    # ── Shared guard ─────────────────────────────────────────────────────────

    def _in_ticket(self, ctx: commands.Context) -> bool:
        """Returns True if the command is being run inside an active modmail thread."""
        return self.bot.threads.find(channel=ctx.channel) is not None

    # ── Management commands ───────────────────────────────────────────────────

    @commands.group(name="supporthours", invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def supporthours(self, ctx: commands.Context):
        """Support Hours plugin management commands."""
        await ctx.send_help(ctx.command)

    @supporthours.command(name="preview")
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def supporthours_preview(self, ctx: commands.Context):
        """Preview the support hours message that will be sent to users."""
        if not self._in_ticket(ctx):
            return await ctx.send(
                "❌ This command can only be used inside an active modmail ticket channel.",
                delete_after=10,
            )
        embed = self._build_embed()
        now = datetime.now(timezone.utc)
        status = (
            "🔴 **Would NOT send right now** — current time is within support hours."
            if not self._is_outside_hours()
            else "🟢 **Would send right now** — current time is outside support hours."
        )
        await ctx.send(
            f"**Preview of the support hours message sent to users:**\n"
            f"{status} (Current GMT time: `{now.strftime('%H:%M')} GMT`)",
            embed=embed,
        )

    @supporthours.command(name="set")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def supporthours_set(self, ctx: commands.Context, key: str, *, value: str):
        """
        Set a support hours config value.

        Keys: message, title, color, footer, timezone

        Example:
            ?supporthours set timezone EST
            ?supporthours set title 🕐 Our Support Hours
            ?supporthours set color 3498DB
        """
        if not self._in_ticket(ctx):
            return await ctx.send(
                "❌ This command can only be used inside an active modmail ticket channel.",
                delete_after=10,
            )
        valid_keys = {"message", "title", "color", "footer", "timezone"}
        if key not in valid_keys:
            return await ctx.send(
                f"❌ Invalid key `{key}`. Valid keys: `{', '.join(sorted(valid_keys))}`"
            )

        config_key = f"support_hours_{key}"
        self.bot.config[config_key] = value
        await self.bot.config.update()
        await ctx.send(f"✅ `support_hours_{key}` has been updated.")

    @supporthours.command(name="reset")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def supporthours_reset(self, ctx: commands.Context, key: str):
        """
        Reset a support hours config value back to its default.

        Example:
            ?supporthours reset message
        """
        if not self._in_ticket(ctx):
            return await ctx.send(
                "❌ This command can only be used inside an active modmail ticket channel.",
                delete_after=10,
            )
        valid_keys = {"message", "title", "color", "footer", "timezone"}
        if key not in valid_keys:
            return await ctx.send(
                f"❌ Invalid key `{key}`. Valid keys: `{', '.join(sorted(valid_keys))}`"
            )

        config_key = f"support_hours_{key}"
        try:
            del self.bot.config[config_key]
            await self.bot.config.update()
            await ctx.send(f"✅ `{config_key}` has been reset to its default value.")
        except KeyError:
            await ctx.send(f"ℹ️ `{config_key}` was already using the default value.")


async def setup(bot):
    await bot.add_cog(SupportHours(bot))
