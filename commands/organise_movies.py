'''
Created on 27 Feb 2013

@author: 7k
'''
import logging
from optparse import make_option
import os
import re
import requests
import shutil
import sys

from . import BaseCommand, CommandError
from .utils import LibraryCommand
import mlib


RE_SHOW = r'(.+)-?[ ._][s\[]?([0-9]{1,2})[ex]{1,2}([0-9]{1,2})'
RE_SHOW_BBC = r'(.+)-?[ .]([12][0-9]{3})[x.]([01][0-9]\.[0-3][0-9])'
RE_COMPLETE_SEASON = r'(.+)-?[ .thea]{1,4}[ .]complete[ .]season[ .]([0-9]{1,2})'
TMDB_API_BASE = 'https://api.themoviedb.org/3/'
TMDB_API_SEARCH = TMDB_API_BASE + 'search/tv'


class Command(LibraryCommand):
    args = "library_path search_dir"
    option_list = LibraryCommand.option_list + (
        make_option("-m", "--move", dest="move", action="store_true",
                    help="Move files instead of copying."),
        make_option("-a", "--api-key", dest="api_key", default=None,
                    help="The API key for TMDB."),
        make_option("", "--memcache-server", dest="memcache_server",
                    default="127.0.0.1",
                    help="The Memcache server address/host name"),
    )

    def __init__(self):
        super(Command, self).__init__()
        self.cache = None

    def sanitise_show_name(self, name, api_key=None):
        ret = None
        if api_key:
            term = re.sub('[ ._]', '+', name)
            term = re.sub('(?<=[^0-9])(19|2[0-9])[0-9][0-9]$', '', term)
            term = term.lower()
            data = self.cache.get(term)
            if not data and api_key:
                r = requests.get(TMDB_API_SEARCH,
                                 params={'query': term, 'api_key': api_key})
                if r.status_code == 200:
                    data = r.json()
                    self.cache.set(term, data)
            popular = 0
            for result in data['results']:
                if result['popularity'] > 2.0:
                    popular += 1
            if data and 0 < data['total_results'] < 25 and popular < 5:
                ret = data['results'][0]['name']
                ret = ret.rstrip(' -?')
            else:
                logging.debug('Too many results: %s', data['total_results'])

        if not ret:
            ret = re.sub('(?<=[^ .].)\.', ' ', name)
            ret = re.sub('(?<=[0-9])\.', ' ', ret)
            ret = re.sub('(?<= i)\.', ' ', ret, re.I)
            ret = ret.replace('_', ' ').rstrip(' -?')
            if len(ret) > 2 and ret[-2] == '.':
                ret += '.'
            if ret == ret.lower():
                ret = ret.title()
        logging.debug('%s -> %s', name, ret)
        return ret

    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Not enough arguments')
        searchdir = args[0]

        try:
            import memcache
            self.cache = memcache.Client([options.get('memcache_server')])
        except ImportError:
            self.cache = dict()

        paths = mlib.get_movies(searchdir)
        transferred = 0
        failed = 0
        count = 0
        count_max = len(paths)
        logging.info('Found %d movie files', count_max)

        for movie_path in paths:
            count += 1
            prefix = '%5d/%d: ' % (count, count_max)
            logging.info('%sProcessing `%s\'', prefix, movie_path)
            movie_name = os.path.basename(movie_path)
            dir_name = os.path.basename(os.path.dirname(movie_path))
            show = None
            season = None
            episode = None
            dest_file = movie_name.decode('utf8')
            fmt = None

            m = re.match(RE_SHOW, movie_name, re.I)
            if not m:
                m = re.match(RE_SHOW_BBC, movie_name, re.I)
            if not m:
                m = re.match(RE_SHOW, dir_name, re.I)
                if m:
                    fmt = '{} s{}e{} - {}'
            if not m:
                m = re.match(RE_SHOW_BBC, dir_name, re.I)
                if m:
                    fmt = '{} {}.{} - {}'
            if m:
                if fmt:
                    dest_file = fmt.format(m.group(1), m.group(2), m.group(3), dest_file)
                show = m.group(1).replace('_', ' ').rstrip(' -')
                season = int(m.group(2))
                episode = int(m.group(3).replace('.', ''))
            else:
                m = re.match(RE_COMPLETE_SEASON, dir_name, re.I)
                if m:
                    show = m.group(1).replace('_', ' ').rstrip(' -')
                    season = int(m.group(2))
                    m = re.match(RE_SHOW, movie_name, re.I)
                    if m and int(m.group(2)) == season:
                        episode = int(m.group(3))
                        dest_file = '{} s{:02d}e{:02d} - {}'.format(show, season, episode, dest_file)

            if show and season and episode:
                show = self.sanitise_show_name(show, api_key=options['api_key'])
                logging.debug('%sShow name: %s, Season: %s, Episode: %s', prefix, show, season, episode)
                season_path = self.library.path_for_tv_season(show, season)
                try:
                    dest_file = os.path.join(season_path, movie_name.decode('utf8'))
                    logging.debug('%sDestination path: %s', prefix, dest_file)

                    if os.path.exists(dest_file):
                        src_stat = os.stat(movie_path)
                        dst_stat = os.stat(dest_file)
                        if src_stat.st_size == dst_stat.st_size:
                            logging.info('%s%s already exists', prefix, dest_file)
                            continue
                    if options['dry_run']:
                        logging.debug('%sSkipped creation of directory "%s"',
                                      prefix, season_path)
                    else:
                        if not os.path.exists(season_path):
                            logging.debug('Creating directory %s', season_path)
                            os.makedirs(season_path)
                        if options['move']:
                            os.rename(movie_path, dest_file)
                        else:
                            shutil.copy(movie_path, dest_file)
                        transferred += 1
                except Exception as e:
                    import traceback
                    logging.exception('%r: %s', e, movie_path)
                    traceback.print_exc()
                    failed += 1

        logging.info('Transferred %d, failed %d out of %d',
                     transferred, failed, count_max)
