import discord
from discord.ext import commands


class _vclevel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Voice leveling commands"""

    def help_custom(self):
        emoji = "🔊"
        label = "VC Leveling"
        description = "Voice XP, rank and setup"
        return emoji, label, description

    @commands.group()
    async def __VCLeveling__(self, ctx: commands.Context):
        """__**VC Rank**__
`vclevel` , `rankvc`
__**VC Leaderboard**__
`vcleaderboard` , `leaderboard vc`
__**VC Setup**__
`vclevel settings` , `vclevel channel` , `vclevel setxp` , `vclevel setmessage` , `vclevel enable` , `vclevel disable` , `vclevel test` , `vclevel overview`
__**VC Rewards**__
`vclevel rewards` , `vclevel rewards add` , `vclevel rewards list` , `vclevel rewards remove`
__**VC Multipliers**__
`vclevel multiplier` , `vclevel multiplier add` , `vclevel multiplier list` , `vclevel multiplier remove`
__**All Rewards**__
`rewards`"""
