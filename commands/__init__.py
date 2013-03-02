import collections
import imp
import logging
import os
import sys
from optparse import make_option, OptionParser, NO_DEFAULT
import traceback
import warnings

# A cache of loaded commands, so that call_command
# doesn't have to reload every time it's called.
_commands = None


__version__ = '0.1'


class CommandError(Exception):
    pass


class BaseCommand(object):
    # Metadata about this command.
    option_list = (
        make_option(
            '-v', '--verbosity', action='store', dest='verbosity', default='1',
            type='choice', choices=['0', '1', '2', '3'],
            help='Verbosity level; 0=minimal output, 1=normal output, '
            '2=verbose output, 3=very verbose output'
        ),
        make_option(
            '--traceback', action='store_true',
            help='Print traceback on exception'
        ),
    )
    help = ''
    args = ''

    def get_version(self):
        return __version__

    def usage(self, subcommand):
        """
        Return a brief description of how to use this command, by default from
        the attribute ``self.help``.
        """
        usage = '%%prog %s [options] %s' % (subcommand, self.args)
        if self.help:
            return '%s\n\n%s' % (usage, self.help)
        else:
            return usage

    def create_parser(self, prog_name, subcommand):
        """
        Create and return the ``OptionParser`` which will be used to parse the
        arguments to this command.
        """
        return OptionParser(prog=prog_name,
                            usage=self.usage(subcommand),
                            version=self.get_version(),
                            option_list=self.option_list)

    def print_help(self, prog_name, subcommand):
        """
        Print the help message for this command, derived from ``self.usage()``.
        """
        parser = self.create_parser(prog_name, subcommand)
        parser.print_help()

    def run_from_argv(self, argv):
        """
        Set up any environment changes requested, then run this command.
        If the command raises a ``CommandError``, intercept it and print it
        sensibly to stderr.
        """
        parser = self.create_parser(argv[0], argv[1])
        options, args = parser.parse_args(argv[2:])
        try:
            self.execute(*args, **options.__dict__)
        except Exception as e:
            if options.traceback:
                self.stderr.write(traceback.format_exc())
            self.stderr.write('%s: %s' % (e.__class__.__name__, e))
            sys.exit(1)

    def execute(self, *args, **options):
        """
        Execute this command.
        """
        # TODO: styles on stdout/stderr
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        verbosity = int(options['verbosity'])
        levels = [
            logging.ERROR,
            logging.WARNING,
            logging.INFO,
            logging.DEBUG,
        ]
        try:
            level = levels[min(len(levels) - 1, verbosity)]
        except:
            level = logging.ERROR
        logging.basicConfig(level=level,
                            format='%(asctime)s %(levelname)-8s %(message)s')
        output = self.handle(*args, **options)
        if output:
            self.stdout.write(output)

    def handle(self, *args, **options):
        """
        The actual logic of the command. Subclasses must implement
        this method.
        """
        raise NotImplementedError()


def find_commands(command_dir):
    """
    Given a path to a base directory, returns a list of all the command
    names that are available.

    Returns an empty list if no commands are defined.
    """
    try:
        return [f[:-3] for f in os.listdir(command_dir)
                if not f.startswith('_') and f.endswith('.py')]
    except OSError:
        return []


def load_command_class(package, name):
    """
    Given a command name, returns the Command class instance. All errors
    raised by the import process (ImportError, AttributeError) are allowed to
    propagate.
    """
    name = '%s.%s' % (package, name)
    __import__(name)
    return sys.modules[name].Command()


def get_commands():
    """
    Returns a dictionary mapping command names to their callback package.

    This works by looking for a commands package in the current project.
    """
    global _commands
    if _commands is None:
        _commands = dict(
            [(name, 'commands') for name in find_commands(__path__[0])]
        )
    return _commands


def call_command(name, *args, **options):
    """
    Calls the given command, with the given options and args/kwargs.

    This is the primary API you should use for calling specific commands.

    Some examples:
        call_command('syncdb')
        call_command('shell', plain=True)
        call_command('sqlall', 'myapp')
    """
    # Load the command object.
    try:
        package = get_commands()[name]
        if isinstance(package, BaseCommand):
            # If the command is already loaded, use it directly.
            klass = package
        else:
            klass = load_command_class(package, name)
    except KeyError:
        raise CommandError("Unknown command: %r" % name)

    # Grab out a list of defaults from the options. optparse does this for us
    # when the script runs from the command line, but since call_command can
    # be called programatically, we need to simulate the loading and handling
    # of defaults.
    defaults = {}
    for opt in klass.option_list:
        if opt.default is NO_DEFAULT:
            defaults[opt.dest] = None
        else:
            defaults[opt.dest] = opt.default
    defaults.update(options)

    return klass.execute(*args, **defaults)


class LaxOptionParser(OptionParser):
    """
    An option parser that doesn't raise any errors on unknown options.
    """
    def error(self, msg):
        pass

    def print_help(self):
        """Output nothing.

        The lax options are included in the normal option parser, so under
        normal usage, we don't need to print the lax options.
        """
        pass

    def print_lax_help(self):
        """Output the basic options available to every command.

        This just redirects to the default print_help() behavior.
        """
        OptionParser.print_help(self)

    def _process_args(self, largs, rargs, values):
        """
        Overrides OptionParser._process_args to exclusively handle default
        options and ignore args and other options.

        This overrides the behavior of the super class, which stop parsing
        at the first unrecognized option.
        """
        while rargs:
            arg = rargs[0]
            try:
                if arg[0:2] == "--" and len(arg) > 2:
                    # process a single long option (possibly with value(s))
                    # the superclass code pops the arg off rargs
                    self._process_long_opt(rargs, values)
                elif arg[:1] == "-" and len(arg) > 1:
                    # process a cluster of short options (possibly with
                    # value(s) for the last one only)
                    # the superclass code pops the arg off rargs
                    self._process_short_opts(rargs, values)
                else:
                    # it's either a non-default option or an arg
                    # either way, add it to the args list so we can keep
                    # dealing with options
                    del rargs[0]
                    raise Exception
            except:
                largs.append(arg)


class ManagementUtility(object):
    """
    Encapsulates the logic of the management utilities.

    A ManagementUtility has a number of commands, which can be manipulated
    by editing the self.commands dictionary.
    """
    def __init__(self, argv=None):
        self.argv = argv or sys.argv[:]
        self.prog_name = os.path.basename(self.argv[0])

    def main_help_text(self, commands_only=False):
        """
        Returns the script's main help text, as a string.
        """
        if commands_only:
            usage = sorted(get_commands().keys())
        else:
            usage = [
                "",
                "Type '%s help <subcommand>' for help on a specific "
                "subcommand." % self.prog_name,
                "",
                "Available subcommands:",
            ]
            commands_dict = collections.defaultdict(lambda: [])
            for name, package in get_commands().items():
                package = package.rpartition('.')[-1]
                commands_dict[package].append(name)
            # style = color_style()
            for package in sorted(commands_dict.keys()):
                usage.append("")
                #usage.append(style.NOTICE("[%s]" % app))
                usage.append(package)
                for name in sorted(commands_dict[package]):
                    usage.append("    %s" % name)
        return '\n'.join(usage)

    def fetch_command(self, subcommand):
        """
        Tries to fetch the given subcommand, printing a message with the
        appropriate command called from the command line if it can't be found.
        """
        try:
            package = get_commands()[subcommand]
        except KeyError:
            sys.stderr.write(
                "Unknown command: %r\nType '%s help' for usage.\n" %
                (subcommand, self.prog_name)
            )
            sys.exit(1)
        if isinstance(package, BaseCommand):
            # If the command is already loaded, use it directly.
            klass = package
        else:
            klass = load_command_class(package, subcommand)
        return klass

    def autocomplete(self):
        """
        Output completion suggestions for BASH.

        The output of this function is passed to BASH's `COMREPLY` variable and
        treated as completion suggestions. `COMREPLY` expects a space
        separated string as the result.

        The `COMP_WORDS` and `COMP_CWORD` BASH environment variables are used
        to get information about the cli input. Please refer to the BASH
        man-page for more information about this variables.

        Subcommand options are saved as pairs. A pair consists of
        the long option string (e.g. '--exclude') and a boolean
        value indicating if the option requires arguments. When printing to
        stdout, a equal sign is appended to options which require arguments.

        Note: If debugging this function, it is recommended to write the debug
        output in a separate file. Otherwise the debug output will be treated
        and formatted as potential completion suggestions.
        """
        # Don't complete if user hasn't sourced bash_completion file.
        if 'MLIB_AUTO_COMPLETE' not in os.environ:
            return

        cwords = os.environ['COMP_WORDS'].split()[1:]
        cword = int(os.environ['COMP_CWORD'])

        try:
            curr = cwords[cword - 1]
        except IndexError:
            curr = ''

        subcommands = list(get_commands()) + ['help']
        options = [('--help', None)]

        # subcommand
        if cword == 1:
            print(' '.join(sorted(filter(lambda x: x.startswith(curr),
                                         subcommands))))
        # subcommand options
        # special case: the 'help' subcommand has no options
        elif cwords[0] in subcommands and cwords[0] != 'help':
            subcommand_cls = self.fetch_command(cwords[0])
            options += [(s_opt.get_opt_string(), s_opt.nargs) for s_opt in
                        subcommand_cls.option_list]
            # filter out previously specified options from available options
            prev_opts = [x.split('=')[0] for x in cwords[1:cword - 1]]
            options = [opt for opt in options if opt[0] not in prev_opts]

            # filter options by current input
            options = sorted(
                [(k, v) for k, v in options if k.startswith(curr)]
            )
            for option in options:
                opt_label = option[0]
                # append '=' to options which require args
                if option[1]:
                    opt_label += '='
                print(opt_label)
        sys.exit(1)

    def execute(self):
        """
        Given the command-line arguments, this figures out which subcommand is
        being run, creates a parser appropriate to that command, and runs it.
        """
        # Preprocess options to extract --settings and --pythonpath.
        # These options could affect the commands that are available, so they
        # must be processed early.
        parser = LaxOptionParser(usage="%prog subcommand [options] [args]",
                                 version=__version__,
                                 option_list=BaseCommand.option_list)
        self.autocomplete()
        try:
            _options, args = parser.parse_args(self.argv)
        except:
            pass  # Ignore any option errors at this point.

        try:
            subcommand = self.argv[1]
        except IndexError:
            subcommand = 'help'  # Display help if no arguments were given.

        if subcommand == 'help':
            if len(args) <= 2:
                parser.print_lax_help()
                sys.stdout.write(self.main_help_text() + '\n')
            elif args[2] == '--commands':
                sys.stdout.write(
                    self.main_help_text(commands_only=True) + '\n')
            else:
                self.fetch_command(args[2]).print_help(self.prog_name, args[2])
        elif subcommand == 'version':
            sys.stdout.write(parser.get_version() + '\n')
        elif self.argv[1:] == ['--version']:
            # LaxOptionParser already takes care of printing the version.
            pass
        elif self.argv[1:] in (['--help'], ['-h']):
            parser.print_lax_help()
            sys.stdout.write(self.main_help_text() + '\n')
        else:
            self.fetch_command(subcommand).run_from_argv(self.argv)


def execute_from_command_line(argv=None):
    """
    A simple method that runs a ManagementUtility.
    """
    utility = ManagementUtility(argv)
    utility.execute()
