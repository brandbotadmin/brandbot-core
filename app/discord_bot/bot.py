import logging
import discord
from discord.ext import commands
import asyncio
from config.settings import settings

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def start_discord_bot():
    if settings.DISCORD_BOT_TOKEN and not settings.DISCORD_BOT_TOKEN.startswith("your_"):
        asyncio.create_task(bot.start(settings.DISCORD_BOT_TOKEN))


from datetime import datetime

async def send_trading_alert(signal_data: dict) -> None:
    if not settings.DISCORD_BOT_TOKEN or not settings.DISCORD_ALERT_CHANNEL_ID:
        logger.warning("Discord alert skipped (token/channel not configured)")
        return
    if not bot.is_ready():
        logger.warning("Discord bot not ready; alert skipped")
        return
    try:
        channel = bot.get_channel(settings.DISCORD_ALERT_CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(settings.DISCORD_ALERT_CHANNEL_ID)
            
        # Nëse merr tekst të thjeshtë, e përshtat ose krijon Embed-in
        if isinstance(signal_data, str):
            await channel.send(signal_data)
            return

        action = str(signal_data.get("action", "BUY")).upper()
        symbol = str(signal_data.get("symbol", "XAUUSD")).upper()
        is_buy = action == "BUY"
        color = 0x2ECC71 if is_buy else 0xE74C3C  # Gjelbër / Kuqe
        emoji = "🟢" if is_buy else "🔴"

        embed = discord.Embed(
            title=f"{emoji} BRANDBOT SDR SIGNAL | {symbol} ({action})",
            description="Institutional setup verified via **SMC & CRT** validation engine.",
            color=color,
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="📊 Action", value=f"`{action}`", inline=True)
        embed.add_field(name="⏱️ Timeframe", value=f"`{signal_data.get('timeframe', '15m')}`", inline=True)
        embed.add_field(name="🎯 Entry Price", value=f"`{signal_data.get('entry_price', 'N/A')}`", inline=True)
        embed.add_field(name="🛑 Stop Loss", value=f"`{signal_data.get('sl_price', 'N/A')}`", inline=True)
        embed.add_field(name="💰 Take Profit", value=f"`{signal_data.get('tp_price', 'N/A')}`", inline=True)
        embed.add_field(name="⚙️ Engine", value="`CRT / SMC v2.0`", inline=True)

        embed.set_footer(text="BrandBot Core • Automated Signal Routing")

        await channel.send(embed=embed)
    except Exception:
        logger.exception("Failed to send Discord trading alert")
