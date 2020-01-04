import discord
from discord.ext import commands

from .util import LocalDatabase, SpotifyClient


class VoteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def start(self, ctx):
      channel = self.bot.get_channel(self.bot.config['song_channel'])
      msgs = await channel.history(limit=1).flatten()

      if msgs:
        await ctx.send('There is still a round going.')
      else:
        spot = SpotifyClient.instance()
        round_num = LocalDatabase.get_current_round()+1
        for track in spot.get_all_playlist_tracks(self.bot.config['playlist_id']):
          added = 1 if self.bot.config['debug'] else LocalDatabase.add_song(track, round_num)
          if added:
            msg = await channel.send('https://open.spotify.com/track/{}'.format(track['track']['id']))
            await msg.add_reaction(self.bot.config['yes_vote'])
            await msg.add_reaction(self.bot.config['no_vote'])
            await msg.add_reaction(self.bot.config['abstain_vote'])
        await ctx.send('Starting a new round')

    @commands.command()
    @commands.is_owner()
    async def stop(self, ctx):
      vote_chan = self.bot.get_channel(self.bot.config['song_channel'])
      re_chan = self.bot.get_channel(self.bot.config['result_channel'])

      results = []
      summary = discord.Embed(title='Round {} Summary'.format(LocalDatabase.get_current_round()))

      async for msg in vote_chan.history():
        resp = dict(zip(vote_chan.members, (0 for i in range(len(vote_chan.members)))))
        song_id = msg.content[msg.content.rindex('/')+1:]
        track = SpotifyClient.instance().get_track(song_id)
        for react in msg.reactions:
          if react.emoji == self.bot.config['yes_vote']:
            async for user in react.users():
              resp[user] = 1
          elif react.emoji == self.bot.config['no_vote']:
            async for user in react.users():
              if not resp[user]:
                resp[user] = -1
          # An abstain will retract the user's other vote if they made one.
          elif react.emoji == self.bot.config['abstain_vote']:
            async for user in react.users():
              resp[user] = 0
        score = sum(resp.values())
        if score > 0:
          results.append(track['name'] + ' - Added')
        elif score == 0 and len(LocalDatabase.get_song(song_id)) < 2:
          results.append(track['name'] + ' - Rolled')
        else:
          results.append(track['name'] + ' - Dropped')

        bob = discord.Embed(title=track['name'],
                            description='Score: {} | Round: {}'.format(score, LocalDatabase.get_current_round()))
        resp.pop(self.bot.user)

        bob.add_field(name='Upvoted', value='\n'.join((str(u) for u in resp if resp[u] == 1)) or 'Nobody')
        bob.add_field(name='Downvoted', value='\n'.join((str(u) for u in resp if resp[u] == -1)) or 'Nobody')
        bob.add_field(name='Abstained', value='\n'.join((str(u) for u in resp if resp[u] == 0)) or 'Nobody')

        await re_chan.send(embed=bob)

        if not self.bot.config['debug']:
          LocalDatabase.insert_votes(song_id, resp)

      summary.add_field(name='Results', value='\n'.join(results))
      await (await re_chan.send(embed=summary)).pin()

      await vote_chan.purge()

    
    @commands.command()
    @commands.is_owner()
    async def re_wipe(self, ctx):
      await self.bot.get_channel(self.bot.config['result_channel']).purge()
    
    
    @commands.command()
    @commands.is_owner()
    async def s_wipe(self, ctx):
      await self.bot.get_channel(self.bot.config['song_channel']).purge()

    @commands.command()
    @commands.is_owner()
    async def remind(self, ctx):
      vote_chan = self.bot.get_channel(self.bot.config['song_channel'])
      valid_reacts = (self.bot.config['yes_vote'], self.bot.config['no_vote'], self.bot.config['abstain_vote'])
      voters = set(vote_chan.members)

      left_over = dict(((voter, []) for voter in voters))

      async for msg in vote_chan.history():
        members_reacted = set()
        for react in msg.reactions:
          if react not in valid_reacts:
            continue
          async for user in react.users():
            members_reacted.add(user)

        for voter in (voters - members_reacted):
          song_id = msg.content[msg.content.rindex('/') + 1:]
          track = SpotifyClient.instance().get_track(song_id)
          left_over[voter].append(track)

      print(left_over)


def setup(bot: commands.Bot):
    bot.add_cog(VoteCog(bot))
