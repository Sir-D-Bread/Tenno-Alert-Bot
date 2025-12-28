import requests
import discord
from discord.ext import tasks
from datetime import datetime, timezone

# ================== CONFIG ==================
DISCORD_TOKEN = "TOKEN IF I HAD ONE"
CHANNEL_ID = 1454749390446006285  # replace with your channel ID
PLATFORM = "pc"                  # pc, ps4, xb1, switch
POLL_INTERVAL = 60               # seconds
# ============================================

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Keep track of alert IDs we've already reported (in-memory)
seen_alert_ids = set()


def fetch_alerts():
    """
    Fetch current alerts from warframestat.us for a given platform.
    Returns a list of alert dicts or [] on error.
    """
    url = f"https://api.warframestat.us/{PLATFORM}/alerts"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return []


def expires_in(alert) -> str | None:
    """
    Returns a human-friendly time remaining from alert['expiry'].
    If expiry is missing/unparseable, returns None.
    """
    expiry = alert.get("expiry")
    if not expiry:
        return None

    try:
        # ISO timestamps often end in 'Z' for UTC
        expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)

        seconds = int((expiry_dt - now).total_seconds())
        if seconds <= 0:
            return "Expired"

        hours, rem = divmod(seconds, 3600)
        minutes, _ = divmod(rem, 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return None


def format_alert(alert) -> str:
    """
    Format an alert without printing 'Unknown ...' placeholders.
    Only prints fields that actually exist.
    """
    mission = alert.get("mission", {}) or {}

    mission_type = mission.get("type")
    node = mission.get("node")
    faction = mission.get("faction")
    min_level = mission.get("minEnemyLevel")
    max_level = mission.get("maxEnemyLevel")

    reward = mission.get("reward", {}) or {}
    reward_item = reward.get("itemString") or reward.get("asString")
    credits = reward.get("credits")

    eta = expires_in(alert)

    lines = ["**New Alert!**"]

    # Mission line
    mission_parts = []
    if mission_type:
        mission_parts.append(mission_type)
    if node:
        mission_parts.append(f"@ {node}")
    if mission_parts:
        lines.append(f"**Mission:** {' '.join(mission_parts)}")

    if faction:
        lines.append(f"**Faction:** {faction}")

    # Level line
    if min_level is not None and max_level is not None:
        lines.append(f"**Level:** {min_level}-{max_level}")
    elif min_level is not None:
        lines.append(f"**Level:** {min_level}+")
    elif max_level is not None:
        lines.append(f"**Level:** up to {max_level}")

    # Reward line (avoid "No special reward")
    reward_bits = []
    if reward_item:
        ri = reward_item.strip()
        if ri and ri.lower() != "no special reward":
            reward_bits.append(ri)

    if isinstance(credits, int) and credits > 0:
        reward_bits.append(f"{credits}cr")

    if reward_bits:
        lines.append("**Reward:** " + " + ".join(reward_bits))

    # Expiry line
    if eta:
        lines.append(f"**Expires in:** {eta}")

    return "\n".join(lines)


@tasks.loop(seconds=POLL_INTERVAL)
async def check_alerts():
    await client.wait_until_ready()

    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        print("Channel not found. Check CHANNEL_ID or permissions.")
        return

    alerts = fetch_alerts()

    new_alerts = []
    for alert in alerts:
        alert_id = alert.get("id")
        if alert_id and alert_id not in seen_alert_ids:
            seen_alert_ids.add(alert_id)
            new_alerts.append(alert)

    for alert in new_alerts:
        try:
            await channel.send(format_alert(alert))
        except Exception as e:
            print("Error sending alert to Discord:", e)


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("Starting alert loop...")
    check_alerts.start()


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
