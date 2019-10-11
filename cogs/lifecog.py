import discord
from discord.ext import commands


class LifeCog(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  @commands.is_owner()
  async def refresh(self, ctx):
    print('Refreshing')
    self.bot.load_config()
    self.bot.load_extensions()

  @commands.command()
  @commands.is_owner()
  async def die(self, ctx):
    print('Owner told me to die!')
    await self.bot.close()


def setup(bot):
  bot.add_cog(LifeCog(bot))
