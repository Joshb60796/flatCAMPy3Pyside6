from tclCommands.TclCommand import *


class TclCommandNewExcellon(TclCommandSignaled):
    """Create a new empty Excellon (drill) object."""

    aliases = ['new_excellon']

    arg_names = collections.OrderedDict([
        ('name', str)
    ])

    option_types = collections.OrderedDict()

    required = ['name']

    help = {
        'main': "Creates a new empty Excellon object for adding drill points.",
        'args': collections.OrderedDict([
            ('name', 'New object name.'),
        ]),
        'examples': ['new_excellon holes']
    }

    def execute(self, args, unnamed_args):
        name = args['name']

        def init(obj, app):
            obj.tools = {}
            obj.drills = []
            obj.solid_geometry = []

        self.app.new_object('excellon', str(name), init)
