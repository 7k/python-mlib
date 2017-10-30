#!/usr/bin/env python
'''
Created on 27 Feb 2013

@author: 7k
'''
import os
import re
import sys

DEFAULTS = {
    'movies': 'Movies',
    'music': 'Music',
    'tv': 'TV',
}

RE_MOVIES = re.compile('.*\.(mov|MOV|avi|AVI|mpg|MPG|mp4|MP4|mkv|MKV|nfo)$')
RE_MOVIES_EXCLUDED = re.compile('(Incomplete Downloads|\.AppleDouble)')


def get_movies(searchdir):
    matches = []
    for root, _dirnames, filenames in os.walk(searchdir):
        for filename in filter(lambda n: RE_MOVIES.match(n), filenames):
            if filename.startswith('._'):
                continue
            match = os.path.join(root, filename)
            if RE_MOVIES_EXCLUDED.search(match):
                continue
            matches.append(match)
    return matches


class Library:
    def __init__(self,
                 path,
                 movies=DEFAULTS['movies'],
                 music=DEFAULTS['music'],
                 tv=DEFAULTS['tv'],
                 **kwargs):
        self.paths = {
            'base': path,
            'movies': movies,
            'music': music,
            'tv': tv,
        }

    @property
    def movies_path(self):
        return os.path.join(self.paths['base'], self.paths['movies'])

    @property
    def tv_path(self):
        return os.path.join(self.paths['base'], self.paths['tv'])

    def path_for_tv_season(self, show, season):
        return os.path.join(self.tv_path, show, 'Season %s' % season)


if __name__ == '__main__':
    from commands import execute_from_command_line

    execute_from_command_line(sys.argv)
