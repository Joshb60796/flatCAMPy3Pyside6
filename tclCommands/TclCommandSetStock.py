from tclCommands.TclCommand import *


class TclCommandSetStock(TclCommand):
    """Set PCB material (stock) size. Origin is always (0, 0)."""

    aliases = ['set_stock', 'stock']

    arg_names = collections.OrderedDict([
        ('width', float),
        ('height', float),
    ])

    option_types = collections.OrderedDict([
        ('visible', bool),
    ])

    required = ['width', 'height']

    help = {
        'main': "Set the PCB material rectangle at origin (0, 0).",
        'args': collections.OrderedDict([
            ('width', 'Stock width (X) in project units.'),
            ('height', 'Stock height (Y) in project units.'),
            ('visible', 'Draw the outline (1/0).'),
        ]),
        'examples': ['set_stock 100 70', 'stock 3.937 2.756']
    }

    def execute(self, args, unnamed_args):
        width = float(args['width'])
        height = float(args['height'])
        if width <= 0 or height <= 0:
            self.raise_tcl_error("Stock width and height must be positive.")
        visible = args.get('visible')
        if visible is None:
            self.app.stock.set_size(width, height)
        else:
            self.app.stock.set_size(width, height, visible=bool(visible))
        if getattr(self.app, "stock_tool", None) is not None:
            self.app.stock_tool.load_from_app()
        return "stock %.6g x %.6g" % (width, height)
