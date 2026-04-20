Ticket Mover Plugin for Modmail — Horizon Airways
---------------------------------------------------
Provides commands to move a ticket to a specific category and
automatically notify the user with a transfer message.

Commands (Moderator+):
    ?movegeneral       – Move to General Support
    ?movecomplaints    – Move to Complaints
    ?moverecruitment   – Move to Recruitment
    ?moveupgrades      – Move to Upgrades
    ?movedevelopment   – Move to Development
"""

from __future__ import annotations

import discord
from discord.ext import commands

from core import checks
from core.models import PermissionLevel


# ─── Category map: command name → (category_id, display_name) ─────────────────

CATEGORIES = {
    "movegeneral":      (1495499844079452221, "General Support"),
    "movecomplaints":   (1495499911481786379, "Complaints"),
    "moverecruitment":  (1495500001466384626, "Recruitment"),
    "moveupgrades":     (1495500090134237495, "Upgrades"),
    "movedevelopment":  (1495500164268425256, "Development"),
}

# ──────────────────────────────────────────────────────────────────────────────


def transfer_embed(category_name: str) -> discord.Embed:
    """Build the transfer notification embed sent to the user."""
    embed = discord.Embed(
        description=(
            f"Hello,\n\n"
            f"I've identified that your ticket is best resolved by another team. "
            f"As such, I'm going to transfer this matter to the **{category_name}** category.\n\n"
            f"A member of the relevant team will reach out to support you in this matter.\n\n"
            f"Thanks,\n"
            f"**Automated Ticket Manager**\n"
            f"Horizon Airways"
        ),
        color=0x2C3E8C,  # Horizon Airways navy blue
    )
    embed.set_footer(text="Horizon Airways — Automated Ticket Manager")
    return embed


class TicketMover(commands.Cog):
    """Move modmail tickets between categories with an automated user notification."""

    def __init__(self, bot):
        self.bot = bot

    async def _move(self, ctx: commands.Context, category_id: int, category_name: str):
        """Core logic: send transfer message to user, then move the thread channel."""

        # Must be used inside an active modmail ticket channel
        thread = ctx.bot.threads.find(channel=ctx.channel)
        if thread is None:
            return await ctx.send(
                "❌ This command can only be used inside an active modmail ticket channel.",
                delete_after=10,
            )

        # Resolve the target category
        category = ctx.guild.get_channel(category_id)
        if category is None:
            return await ctx.send(
                f"❌ Could not find category with ID `{category_id}`. "
                "Please check the bot has access to it.",
                delete_after=10,
            )

        if not isinstance(category, discord.CategoryChannel):
            return await ctx.send(
                f"❌ Channel `{category_id}` is not a category.",
                delete_after=10,
            )

        # Send the transfer message to the user via the thread (delivers to their DMs)
        embed = transfer_embed(category_name)
        try:
            await thread.reply(embed=embed)
        except Exception as exc:
            self.bot.logger.error("TicketMover: failed to send transfer message – %s", exc)
            return await ctx.send(
                f"❌ Failed to send transfer message to user: `{exc}`",
                delete_after=10,
            )

        # Move the thread channel into the target category
        try:
            await ctx.channel.edit(category=category, reason=f"Ticket moved to {category_name} by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send(
                "❌ I don't have permission to move this channel. "
                "Please ensure I have `Manage Channels` permission.",
                delete_after=10,
            )
        except Exception as exc:
            self.bot.logger.error("TicketMover: failed to move channel – %s", exc)
            return await ctx.send(f"❌ Failed to move channel: `{exc}`", delete_after=10)

        # Confirm to staff in the thread
        confirm = discord.Embed(
            description=f"✅ Ticket moved to **{category_name}** and user has been notified.",
            color=0x2ECC71,
        )
        await ctx.send(embed=confirm)

        # Delete the invoking command message to keep the thread tidy
        try:
            await ctx.message.delete()
        except Exception:
            pass

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name="movegeneral")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    async def move_general(self, ctx: commands.Context):
        """Move this ticket to the General Support category."""
        await self._move(ctx, *CATEGORIES["movegeneral"])

    @commands.command(name="movecomplaints")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    async def move_complaints(self, ctx: commands.Context):
        """Move this ticket to the Complaints category."""
        await self._move(ctx, *CATEGORIES["movecomplaints"])

    @commands.command(name="moverecruitment")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    async def move_recruitment(self, ctx: commands.Context):
        """Move this ticket to the Recruitment category."""
        await self._move(ctx, *CATEGORIES["moverecruitment"])

    @commands.command(name="moveupgrades")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    async def move_upgrades(self, ctx: commands.Context):
        """Move this ticket to the Upgrades category."""
        await self._move(ctx, *CATEGORIES["moveupgrades"])

    @commands.command(name="movedevelopment")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    async def move_development(self, ctx: commands.Context):
        """Move this ticket to the Development category."""
        await self._move(ctx, *CATEGORIES["movedevelopment"])


async def setup(bot):
    await bot.add_cog(TicketMover(bot))
