import datetime
import os
import sqlite3

from math import ceil

import requests

from requests.auth import HTTPBasicAuth

with open(os.path.join(os.path.dirname(__file__), 'spot.key'), 'r') as f:
  C_ID = f.readline().strip()
  C_SEC = f.readline().strip()


class SpotURLs(object):
  AUTH_PATH = 'https://accounts.spotify.com/api/token'
  API_PATH = 'https://api.spotify.com/v1/'

  PLAYLIST_PATH = 'playlists/'
  SEARCH_PATH = 'search/'
  TRACK_PATH = 'tracks/'
  USER_PATH = 'users/'


RATE_LIMITED = -234

VALID_SEARCH_TYPES = ('album', 'artist', 'playlist', 'track')


class SpotifyClient(object):
  ins = None

  def __init__(self, **kwargs):
    global C_ID, C_SEC

    if self.ins is None:
      SpotifyClient.ins = self

    self.cid = kwargs.get('id', C_ID)
    self.csec = kwargs.get('secret', C_SEC)

    self.token = None
    self.exp = None
    self.wait_time = None

  @classmethod
  def instance(cls):
    if cls.ins is None:
      cls()
    return cls.ins

  @staticmethod
  def get_id(spot_share_str):
    spot_str = spot_share_str.strip()
    if spot_str.count(':') != 2 or spot_str.split(':')[0] != 'spotify':
      return ''  # If not valid share string from spotify
    return spot_str.split(':')[-1]

  def _page_generator(self, page, k):
    """Spotify has some pages that return a list of objects along with a link to the next page.
    This returns a generator that will get every item from the pages. We need the item name to use as a key for the dictionary."""

    while page is not None:
      for i in page[k]['items']:
        yield i
      page = self.make_auth_request(page[k]['next']).json() if page[k]['next'] else None

  def is_token_valid(self):
    return self.token is not None and datetime.datetime.now() < self.exp

  def refresh_token(self):
    if self.is_token_valid():
      return None  # No need to update the token, its still good.

    out = requests.post(SpotURLs.AUTH_PATH,
                        params={'grant_type': 'client_credentials'},
                        headers={'Content-Type': 'application/x-www-form-urlencoded'},
                        auth=HTTPBasicAuth(self.cid, self.csec))

    self.token = out.json()['access_token']
    self.exp = datetime.datetime.now() + datetime.timedelta(seconds=out.json()['expires_in'])

  def make_auth_request(self, url, headers=None, **kwargs):
    if not self.is_token_valid():
      self.refresh_token()

    h = headers or {}
    h.update({'Authorization': 'Bearer ' + self.token})
    h.update(kwargs.pop('headers', {}))

    if self.wait_time is None or self.wait_time < datetime.datetime.now():
      res = requests.get(url, headers=h, **kwargs)
      if res.status_code == 429:
        self.wait_time = datetime.datetime.now() + datetime.timedelta(seconds=res.headers['Retry-After'])
        return RATE_LIMITED
      return res
    else:
      return RATE_LIMITED

  def get_user(self, uid):
    res = self.make_auth_request(SpotURLs.API_PATH + SpotURLs.USER_PATH + uid)
    if res != RATE_LIMITED and res.status_code == 200:
      return res.json()
    return res

  def get_playlist(self, pid, fields=None):
    kwargs = {'params': {}}
    if fields is not None:
      kwargs['params']['fields'] = ','.join(fields)

    res = self.make_auth_request(SpotURLs.API_PATH + SpotURLs.PLAYLIST_PATH + pid, **kwargs)
    if res != RATE_LIMITED and res.status_code == 200:
      return res.json()
    return None

  def get_all_playlist_tracks(self, pid):
    play = self.get_playlist(pid)

    while play is not None:
      for t in play['tracks']['items']:
        yield t
      play = self.make_auth_request(play['tracks']['next']).json() if play['tracks']['next'] is not None else None
    raise StopIteration

  def get_track(self, spot_id):
    res = self.make_auth_request(SpotURLs.API_PATH + SpotURLs.TRACK_PATH + spot_id)
    if res != RATE_LIMITED and res.status_code == 200:
      return res.json()
    return None

  def get_tracks(self, spot_ids):
    reqs = int(ceil(len(spot_ids) / 50))
    data = {'tracks': []}

    for i in range(reqs):
      params = {'ids': ','.join(spot_ids[i * 50: (i + 1) * 50])}  # Spotify will only return a max of 50 tracks at once.
      res = self.make_auth_request(SpotURLs.API_PATH + SpotURLs.TRACK_PATH, params=params)
      if res is not None and res.status_code == 200:
        data['tracks'].extend(res.json()['tracks'])

    return data

  def search(self, q, t=(VALID_SEARCH_TYPES[-1],)):
    for i in t:
      if i not in VALID_SEARCH_TYPES:
        raise ValueError('Every element in t must be in VALID_SEARCH_TYPES')

    p = {'q': q, 'type': ','.join(t)}

    res = self.make_auth_request(SpotURLs.API_PATH + SpotURLs.SEARCH_PATH, params=p)
    if res != RATE_LIMITED and res.status_code == 200:
      j = res.json()
      ret = {}
      for i in t:
        k = i.lower()
        # For some reason, they decided to make type lack the s that is used as the dict key.
        ret[k] = {'items': self._page_generator(j, k + 's'), 'total': j[k + 's']['total']}
      return ret
    return None


class LocalDatabase(object):
  db_path = os.path.join(os.getcwd(), 'data.db')

  @staticmethod
  def check():
    if not os.path.isfile(LocalDatabase.db_path):
      with sqlite3.connect(LocalDatabase.db_path) as conn:
        conn.execute('CREATE TABLE songs(spot_id TEXT, round INTEGER, added_by TEXT, rollover BOOLEAN)')
        conn.execute('CREATE TABLE votes(user TEXT, value INTEGER, round INTEGER, song TEXT)')

  @staticmethod
  def get_song(song_id):
    LocalDatabase.check()
    with sqlite3.connect(LocalDatabase.db_path) as conn:
      cur = conn.cursor()

      cur.execute('SELECT * FROM songs WHERE spot_id=?', (song_id,))
      results = cur.fetchall()

      cur.close()
    return results

  @staticmethod
  def get_score(song_id, rollover=False):
    LocalDatabase.check()
    with sqlite3.connect(LocalDatabase.db_path) as conn:
      cur = conn.cursor()

      cur.execute("SELECT * FROM votes WHERE song=? ORDER BY round ASC", (song_id,))
      results = cur.fetchall()
      if rollover:
        new_round = results[0][2] + 1
        results = [x for x in results if x[2] == new_round]

      score = sum((x[1] for x in results)) if results else None

      cur.close()
    return score

  @staticmethod
  def get_current_round():
    LocalDatabase.check()
    with sqlite3.connect(LocalDatabase.db_path) as conn:
      cur = conn.cursor()

      cur.execute('SELECT round FROM songs ORDER BY round DESC LIMIT 1')
      result = cur.fetchone()

      if not result:
        result = (-1,)

      cur.close()
    return result[0]

  @staticmethod
  def insert_votes(song, votes: dict):
    LocalDatabase.check()
    with sqlite3.connect(LocalDatabase.db_path) as conn:
      r_id = LocalDatabase.get_current_round()
      values = [(str(k), v, r_id, song) for k, v in votes.items()]

      conn.executemany("INSERT INTO votes VALUES (?, ?, ?, ?)", values)

  @staticmethod
  def add_song(s_info, round_):
    added = True
    with sqlite3.connect(LocalDatabase.db_path) as conn:
      cur = conn.cursor()
      song = s_info['track']['id']

      cur.execute("SELECT * FROM songs WHERE spot_id=?", (song,))
      results = cur.fetchall()

      # Rollover attempt.
      if len(results) == 1 and LocalDatabase.get_score(song) == 0:
        cur.execute("INSERT INTO songs VALUES (?, ?, ?, ?)", (song, round_, s_info['added_by']['id'], 1))
      # New song.
      elif not len(results):
        cur.execute("INSERT INTO songs VALUES (?, ?, ?, ?)", (song, round_, s_info['added_by']['id'], 0))
      # Nope.
      else:
        print('Song {} not added. It can\'t rollover.'.format(song))
        added = False

      cur.close()

    return added


def is_num(s):
  try:
    float(s)
    return True
  except ValueError:
    return False
