from tclCommands.TclCommand import *


class TclCommandPlaceOnStock(TclCommand):
    """Move an object so its min corner is at (x, y) on the stock."""

    aliases = ['place_on_stock', 'place']

    arg_names = collections.OrderedDict([
        ('name', str),
        ('x', float),
        ('y', float),
    ])

    option_types = collections.OrderedDict()

    required = ['name', 'x', 'y']

    help = {
        'main': "Move an object so its bottom-left sits at (x, y) on the stock.",
        'args': collections.OrderedDict([
            ('name', 'Object name.'),
            ('x', 'Target X of the min corner.'),
            ('y', 'Target Y of the min corner.'),
        ]),
        'examples': ['place_on_stock top 2 3']
    }

    def execute(self, args, unnamed_args):
        name = args['name']
        obj = self.app.collection.get_by_name(name)
        if obj is None:
            self.raise_tcl_error("Object not found: %s" % name)
        dx, dy = self.app.stock.translate_objects(
            [obj], args['x'], args['y'], absolute=True
        )
        return "placed %s at (%.6g, %.6g) delta=(%.6g, %.6g)" % (
            name, args['x'], args['y'], dx, dy
        )
