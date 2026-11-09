import discord
from utils.emoji import LEVEL_UP
from discord.ext import commands


class _leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Chat leveling commands"""

    def help_custom(self):
        emoji = LEVEL_UP
        label = "Chat Leveling"
        description = "Chat XP, rank and setup"
        return emoji, label, description

    @commands.group()
    async def __Leveling__(self, ctx: commands.Context):
        """__**Chat Rank**__
`chatrank` (alias `cr`)
__**Leaderboards**__
`leaderboard` , `leaderboard chat` , `leaderboard vc` , `leaderboard schedule` , `leaderboard live` , `leaderboard liveinterval`
__**XP Settings**__
`chatlevel` , `chatlevel settings` , `chatlevel setxp` , `chatlevel setmessage` , `chatlevel setcolor` , `chatlevel thumbnail` , `chatlevel cooldown` , `chatlevel channel` , `chatlevel enable` , `chatlevel disable`
__**Rewards & Roles**__
`chatlevel rewards` , `chatlevel rewards add` , `chatlevel rewards list` , `chatlevel rewards remove` , `setlevelrole` , `removelevelrole` , `listlevelroles`
__**Multipliers & Blacklist**__
`chatlevel multiplier` , `chatlevel multiplier add` , `chatlevel multiplier list` , `chatlevel multiplier remove` , `chatlevel blacklist` , `chatlevel blacklist add` , `chatlevel blacklist list` , `chatlevel blacklist remove`
__**Utilities**__
`chatlevel overview` , `chatlevel placeholders` , `chatlevel stats` , `chatlevel test` , `setxp` , `resetxp` , `setlevel`"""
