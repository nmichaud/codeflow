# Standard library imports
import logging

# Enthought library imports.
from envisage.core_plugin import CorePlugin
from envisage.ui.tasks.tasks_plugin import TasksPlugin

# Local imports
from plugins.twisted.plugin import TwistedPlugin
from plugins.debugger.plugin import DebuggerPlugin

from app.application import DebuggerApplication

def main(argv):
    """ Run the application

    """
    logging.basicConfig(level=logging.WARNING)

    plugins = [CorePlugin(),
               TasksPlugin(),
               TwistedPlugin(),
               DebuggerPlugin(),
               ]

    app = DebuggerApplication(plugins=plugins)
    app.run()

    logging.shutdown()


if __name__ == '__main__':
    import sys
    main(sys.argv)
