import logging
from optparse import make_option
import os
import re
import requests
import shutil
import sys

from . import BaseCommand, CommandError
import mlib


class LibraryCommand(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option("", "--music", dest="music", default=mlib.DEFAULTS['music'],
                    help="The music folder name inside the library."),
        make_option("", "--movies", dest="movies", default=mlib.DEFAULTS['movies'],
                    help="The movies folder name inside the library."),
        make_option("", "--tv", dest="movies", default=mlib.DEFAULTS['tv'],
                    help="The movies folder name inside the library."),
        make_option("-d", "--dry-run", dest="dry_run", action="store_true",
                    help="Do everything except actually add the note "
                    "to the affected change."),
    )

    def __init__(self):
        self.library = None
        self.stdout = None
        self.stderr = None

    def execute(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Not enough arguments')

        self.library = mlib.Library(os.getcwd(), **options)

        super(LibraryCommand, self).execute(*args, **options)
