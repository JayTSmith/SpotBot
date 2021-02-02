import json
import os
import sys

from discord import Intents
from discord.ext import commands


CONFIG_PATH = 'data/config.json'
COG_PATH = 'cogs'
DEBUG_CONFIG_PATH = 'data/debug_config.json'
STRINGS_PATH = 'data/strings.json'

INTENTS = Intents.default()
INTENTS.members = True

class SpotBot(commands.Bot):
  def __init__(self, debug=0, *args, **kwargs):
    super(SpotBot, self).__init__(*args, **kwargs)

    self.config = None
    self.strings = None

    self.load_config(debug)
    self.load_extensions()

  def load_config(self, debug):
    conf = DEBUG_CONFIG_PATH if debug else CONFIG_PATH

    print(f'Loading configuration({conf})...', end='')

    c_f = open(conf, encoding='utf8')
    self.config = json.load(c_f)
    c_f.close()

    s_f = open(STRINGS_PATH, encoding='utf8')
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

d = '--debug' in sys.argv
print(f'Running bot in {"Normal" if not d else "Debug"} mode')
bot = SpotBot(debug=d, command_prefix='$', intents=INTENTS)

bot.run(bot.config['token'])