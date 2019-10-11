import asyncio
import json
import os
from random import choice

import discord
from discord.ext import commands


CONFIG_PATH = 'data/config.json'
COG_PATH = 'cogs'
STRINGS_PATH = 'data/strings.json'


class SpotBot(commands.Bot):
  def __init__(self, *args, **kwargs):
    super(SpotBot, self).__init__(*args, **kwargs)

    self.config = None
    self.strings = None

    self.load_config()
    self.load_extensions()

  def load_config(self):
    print('Loading configuration...', end='')
    c_f = open(CONFIG_PATH)
    self.config = json.load(c_f)
    c_f.close()

    s_f = open(STRINGS_PATH)
    self.strings = json.load(s_f)
    s_f.close()
    print('Done')

  def load_extensions(self):
    global COG_PATH

    print('Loading extensions.')
    for f in (x[:x.index('.py')] for x in os.listdir(COG_PATH) if x.endswith('cog.py')):
      ext_name = COG_PATH + '.{}'.format(f)
      if ext_name in self.extensions:
        print('{} reloaded!'.format(ext_name))
        self.reload_extension(ext_name)
      else:
        print('{} loaded!'.format(ext_name))
        self.load_extension(ext_name)
    print('Done with extensions.')

bot = SpotBot(command_prefix='$')

bot.run(bot.config['token'])