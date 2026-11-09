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
`chatlevel` , `rankchat`
__**Leaderboards**__
`leaderboard` , `leaderboard chat` , `leaderboard schedule` , `leaderboard live`
__**XP Settings**__
`level` , `level settings` , `level setxp` , `level setmessage` , `level setcolor` , `level thumbnail` , `level cooldown` , `level channel` , `level enable` , `level disable`
__**Rewards & Roles**__
`level rewards` , `level rewards add` , `level rewards list` , `level rewards remove` , `setlevelrole` , `removelevelrole` , `listlevelroles`
__**Multipliers & Blacklist**__
`level multiplier` , `level multiplier add` , `level multiplier list` , `level multiplier remove` , `level blacklist` , `level blacklist add` , `level blacklist list` , `level blacklist remove`
__**Utilities**__
`level overview` , `rewards` , `level placeholders` , `level stats` , `level test` , `setxp` , `resetxp` , `setlevel`"""
