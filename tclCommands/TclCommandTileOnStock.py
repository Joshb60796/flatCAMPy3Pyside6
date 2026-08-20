from tclCommands.TclCommand import *
from stock import autofill_counts, size_of


class TclCommandTileOnStock(TclCommandSignaled):
    """Rectilinear array of an object across the PCB material."""

    aliases = ['tile_on_stock', 'tile']

    arg_names = collections.OrderedDict([
        ('name', str),
    ])

    option_types = collections.OrderedDict([
        ('columns', int),
        ('rows', int),
        ('spacing_x', float),
        ('spacing_y', float),
        ('spacing', float),
        ('margin', float),
        ('autofill', bool),
        ('origin', bool),
        ('keep', bool),
        ('outname', str),
    ])

    required = ['name']

    help = {
        'main': "Tile an object in a grid on the PCB material.",
        'args': collections.OrderedDict([
            ('name', 'Object to tile.'),
            ('columns', 'Copies in X.'),
            ('rows', 'Copies in Y.'),
            ('spacing_x', 'Gap between columns.'),
            ('spacing_y', 'Gap between rows.'),
            ('spacing', 'Gap used for both axes if X/Y omitted.'),
            ('margin', 'Inset from stock origin when starting at origin.'),
            ('autofill', 'Compute columns/rows that fill the stock.'),
            ('origin', 'Start the array at origin+margin (default 1).'),
            ('keep', 'Keep the original object (default 0: replace it).'),
            ('outname', 'Name of the new object (default name_tile).'),
        ]),
        'examples': [
            'tile_on_stock top -autofill 1 -spacing 2 -margin 2',
            'tile_on_stock top -columns 4 -rows 3 -spacing_x 1 -spacing_y 1',
        ]
    }

    def execute(self, args, unnamed_args):
        name = args['name']
        obj = self.app.collection.get_by_name(name)
        if obj is None:
            self.raise_tcl_error("Object not found: %s" % name)

        spacing = args.get('spacing')
        spacing_x = args.get('spacing_x', spacing if spacing is not None else 0.0)
        spacing_y = args.get('spacing_y', spacing if spacing is not None else 0.0)
        margin = args.get('margin', 0.0)
        start_at_origin = True if 'origin' not in args else bool(args['origin'])

        columns = args.get('columns')
        rows = args.get('rows')
        if args.get('autofill') or columns is None or rows is None:
            box = obj.bounds()
            dw, dh = size_of(box)
            columns, rows = autofill_counts(
                dw, dh,
                self.app.stock.width(), self.app.stock.height(),
                spacing_x, spacing_y, margin,
            )
        if columns < 1 or rows < 1:
            self.raise_tcl_error("Design does not fit on the stock.")

        created = self.app.stock.tile_objects(
            [obj], columns, rows, spacing_x, spacing_y, margin,
            start_at_origin=start_at_origin,
            outname=args.get('outname'),
            replace_originals=not bool(args.get('keep')),
        )
        new_obj = created[0] if created else None
        if new_obj is None:
            self.raise_tcl_error("Tiling produced no object.")
        return new_obj.options.get('name')
