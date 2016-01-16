'''
Created on 27 Feb 2013

@author: 7k
'''
import logging
from optparse import make_option
import os
import re
import shutil
import sys

from . import BaseCommand, CommandError
import mlib


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
    )

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Not enough arguments')
        librarydir = args[0]
        searchdir = args[1]

        library = mlib.Library(librarydir,
                               music=options['music'],
                               movies=options['movies'])
        paths = mlib.get_movies(searchdir)
        count = 0
        count_max = len(paths)
        logging.info('Found %d movie files', count_max)

        for movie_path in paths:
            count += 1
            logging.info('%5d/%d: Processing `%s\'', count, count_max, movie_path)
            movie_name = os.path.basename(movie_path)
            name = movie_name.replace('.', ' ')
            dir_name = os.path.dirname(movie_path)
            dir_name = dir_name.replace('.', ' ')
            m = re.match(r'(.+) [Ss]?([0-9]{1,2})[Eex]([0-9]{1,2})', name)
            if not m:
                m = re.match(r'(.+) [Ss]?([0-9]{1,2})[Eex]([0-9]{1,2})', dir_name)
            if m:
                logging.debug(m.groups())
                show = m.group(1).replace('_', ' ').title()
                season = int(m.group(2))
                episode = int(m.group(3))
                season_path = library.path_for_tv_season(show, season)
                try:
                    if options['dry_run']:
                        logging.debug('Skipped creation of directory "%s"', season_path)
                    else:
                        if not os.path.exists(season_path):
                            logging.debug('Creating directory %s', season_path)
                            os.makedirs(season_path)
                        dest_file = os.path.join(season_path, movie_name)
                        if options['move']:
                            os.rename(movie_path, dest_file)
                        else:
                            if os.path.exists(dest_file):
                                logging.info('%s already exists', dest_file)
                            else:
                                shutil.copy(movie_path, dest_file)
                except Exception as e:
                    logging.error(e)
