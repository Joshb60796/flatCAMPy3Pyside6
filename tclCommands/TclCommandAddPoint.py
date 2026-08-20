from tclCommands.TclCommand import *


class TclCommandAddPoint(TclCommandSignaled):
    """Add a point to a Geometry object (plunged when generating a CNC job)."""

    aliases = ['add_point']

    arg_names = collections.OrderedDict([
        ('name', str),
        ('x', float),
        ('y', float),
    ])

    option_types = collections.OrderedDict()

    required = ['name', 'x', 'y']

    help = {
        'main': "Adds a point to a Geometry object (drill/plunge location).",
        'args': collections.OrderedDict([
            ('name', 'Geometry object name.'),
            ('x', 'X coordinate.'),
            ('y', 'Y coordinate.'),
        ]),
        'examples': ['add_point geo 1.0 2.0']
    }

    def execute(self, args, unnamed_args):
        name = args['name']
        obj = self.app.collection.get_by_name(name)
        if obj is None:
            self.raise_tcl_error("Object not found: %s" % name)

        if not isinstance(obj, FlatCAMGeometry):
            self.raise_tcl_error('Expected FlatCAMGeometry, got %s %s.' % (name, type(obj)))

        obj.add_point((args['x'], args['y']))
        obj.plot()
