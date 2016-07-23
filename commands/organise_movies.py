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
import mlib


RE_SHOW = r'(.+)-?[ .][s\[]?([0-9]{1,2})[ex]([0-9]{1,2})'
TMDB_API_BASE = 'https://api.themoviedb.org/3/'
TMDB_API_SEARCH = TMDB_API_BASE + 'search/tv'


class Command(BaseCommand):
    args = "library_path search_dir"
    option_list = BaseCommand.option_list + (
        make_option("", "--music", dest="music", default=mlib.DEFAULTS['music'],
                    help="The music folder name inside the library."),
        make_option("", "--movies", dest="movies", default=mlib.DEFAULTS['movies'],
                    help="The movies folder name inside the library."),
        make_option("-d", "--dry-run", dest="dry_run", action="store_true",
                    help="Do everything except actually add the note "
                    "to the affected change."),
        make_option("-m", "--move", dest="move", action="store_true",
                    help="Move files instead of copying."),
        make_option("-a", "--api-key", dest="api_key", default=None,
                    help="The API key for TMDB."),
        make_option("", "--memcache-server", dest="memcache_server",
                    default="127.0.0.1",
                    help="The Memcache server address/host name"),
    )

    def __init__(self):
        self.cache = None

    def sanitise_show_name(self, name, api_key=None):
        ret = None
        name = re.sub('[ ._]', '+', name)
        name = re.sub('(?<=[^0-9])(19|2[0-9])[0-9][0-9]$', '', name)
        name = name.lower()
        data = self.cache.get(name)
        if not data and api_key:
            r = requests.get(TMDB_API_SEARCH,
                             params={'query': name, 'api_key': api_key})
            if r.status_code == 200:
                data = r.json()
                self.cache.set(name, data)
        if data and 0 < data['total_results'] < 5:
            ret = data['results'][0]['name']
            logging.debug('%s -> %s', name, ret)
        return ret

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Not enough arguments')
        librarydir = args[0]
        searchdir = args[1]

        try:
            import memcache
            self.cache = memcache.Client([options.get('memcache_server')])
        except ImportError:
            self.cache = dict()

        library = mlib.Library(librarydir,
                               music=options['music'],
                               movies=options['movies'])
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
            m = re.match(RE_SHOW, movie_name, re.I)
            if not m:
                m = re.match(RE_SHOW, dir_name, re.I)
            if m:
                logging.debug(m.groups())
                show = m.group(1).replace('_', ' ').rstrip(' -')
                s = self.sanitise_show_name(show, api_key=options['api_key'])
                if not s:
                    show = re.sub('(?<=[^ .].)\.', ' ', show)
                    show = re.sub('(?<=[0-9])\.', ' ', show)
                    show = re.sub('(?<= i)\.', ' ', show, re.I)
                    show = show.replace('_', ' ').rstrip(' -')
                    if len(show) > 2 and show[-2] == '.':
                        show += '.'
                    if show == show.lower():
                        show = show.title()
                else:
                    show = s

                logging.debug('%sShow name: %s', prefix, show)
                season = int(m.group(2))
                episode = int(m.group(3))
                season_path = library.path_for_tv_season(show, season)
                try:
                    dest_file = os.path.join(season_path, movie_name)
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
                    logging.error(e)
                    failed += 1

        logging.info('Transferred %d, failed %d out of %d',
                     transferred, failed, count_max)
