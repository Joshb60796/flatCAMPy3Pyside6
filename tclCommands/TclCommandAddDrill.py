from tclCommands.TclCommand import *


class TclCommandAddDrill(TclCommandSignaled):
    """Add a drill point to an Excellon object."""

    aliases = ['add_drill']

    arg_names = collections.OrderedDict([
        ('name', str),
        ('x', float),
        ('y', float),
    ])

    option_types = collections.OrderedDict([
        ('dia', float),
        ('tool', str),
    ])

    required = ['name', 'x', 'y']

    help = {
        'main': "Adds a drill point to an Excellon object.",
        'args': collections.OrderedDict([
            ('name', 'Excellon object name.'),
            ('x', 'X coordinate.'),
            ('y', 'Y coordinate.'),
            ('dia', 'Hole diameter (creates or reuses a tool).'),
            ('tool', 'Existing or new tool name.'),
        ]),
        'examples': [
            'add_drill holes 1.0 2.0 -dia 0.8',
            'add_drill holes 3.0 4.0 -tool 1 -dia 0.8',
        ]
    }

    def execute(self, args, unnamed_args):
        name = args['name']
        obj = self.app.collection.get_by_name(name)
        if obj is None:
            self.raise_tcl_error("Object not found: %s" % name)

        if not isinstance(obj, FlatCAMExcellon):
            self.raise_tcl_error('Expected FlatCAMExcellon, got %s %s.' % (name, type(obj)))

        dia = args.get('dia')
        tool = args.get('tool')
        if dia is None and tool is None:
            self.raise_tcl_error("Specify -dia and/or -tool.")

        try:
            obj.add_drill(args['x'], args['y'], tool=tool, diameter=dia)
        except ValueError as exc:
            self.raise_tcl_error(str(exc))
        obj.plot()
