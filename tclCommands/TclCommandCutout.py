from tclCommands.TclCommand import *
from camlib import init_board_cutout


class TclCommandCutout(TclCommand):
    """
    Tcl shell command to create a board cutout geometry.

    example:

    """

    # List of all command aliases, to be able use old
    # names for backward compatibility (add_poly, add_polygon)
    aliases = ['cutout']

    # Dictionary of types from Tcl command, needs to be ordered
    arg_names = collections.OrderedDict([
        ('name', str),
    ])

    # Dictionary of types from Tcl command, needs to be ordered,
    # this  is  for options  like -optionname value
    option_types = collections.OrderedDict([
        ('dia', float),
        ('margin', float),
        ('gapsize', float),
        ('gaps', str)
    ])

    # array of mandatory options for current Tcl command: required = {'name','outname'}
    required = ['name']

    # structured help for current command, args needs to be ordered
    help = {
        'main': 'Creates board cutout.',
        'args': collections.OrderedDict([
            ('name', 'Name of the object.'),
            ('dia', 'Tool diameter.'),
            ('margin', 'Margin over bounds.'),
            ('gapsize', 'size of gap.'),
            ('gaps', 'type of gaps.'),
        ]),
        'examples': []
    }

    def execute(self, args, unnamed_args):
        """

        :param args:
        :param unnamed_args:
        :return:
        """

        name = args['name']

        try:
            obj = self.app.collection.get_by_name(str(name))
        except:
            return "Could not retrieve object: %s" % name

        def geo_init_me(geo_obj, app_obj):
            init_board_cutout(
                geo_obj,
                obj.bounds(),
                args['dia'],
                margin=args['margin'],
                gapsize=args['gapsize'],
                gaps=args['gaps'],
            )

        try:
            obj.app.new_object("geometry", name + "_cutout", geo_init_me)
        except Exception as e:
            return "Operation failed: %s" % str(e)
