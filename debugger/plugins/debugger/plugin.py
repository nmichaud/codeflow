# Standard library imports.
import os.path

# Enthought library imports.
from envisage.api import Plugin, ServiceOffer
from envisage.ui.tasks.api import TaskFactory
from traits.api import Any, List, Int


class DebuggerPlugin(Plugin):
    """ The main debugger plugin
    """

    # Extension point IDs.
    PREFERENCES       = 'envisage.preferences'
    PREFERENCES_PANES = 'envisage.ui.tasks.preferences_panes'
    SERVICE_OFFERS    = 'envisage.service_offers'
    TASKS             = 'envisage.ui.tasks.tasks'

    #### 'IPlugin' interface ##################################################

    # The plugin's unique identifier.
    id = 'codetools.debugger'

    # The plugin's name (suitable for displaying to the user).
    name = 'Debugger'

    def stop(self):
        if self._debugger_service:
            self._debugger_service.stop_service()

    #### Contributions to extension points made by this plugin ################

    preferences = List(contributes_to=PREFERENCES)
    preferences_panes = List(contributes_to=PREFERENCES_PANES)
    service_offers = List(contributes_to=SERVICE_OFFERS)
    tasks = List(contributes_to=TASKS)

    ###########################################################################
    # Protected interface.
    ###########################################################################

    debug_port = Int(8000)

    _debugger_service = Any()

    #def _preferences_default(self):
    #    filename = os.path.join(os.path.dirname(__file__), 'preferences.ini')
    #    return [ 'file://' + filename ]

    def _preferences_panes_default(self):
        from preferences import DebuggerPreferencesPane
        return [ DebuggerPreferencesPane ]

    def _service_offers_default(self):
        from debugger_service import DebuggerService
        service_offer = ServiceOffer(
            protocol = DebuggerService,
            factory = self._create_debugger_service,
            )
        return [service_offer]

    def _tasks_default(self):
        return [ TaskFactory(id = 'debugger.debugger_task',
                             factory = self._create_debugger_task,
                             )
               ]

    def _create_debugger_task(self):
        from debugger_task import DebuggerTask

        from .debugger_service import DebuggerService
        service = self.application.get_service(DebuggerService)
        return DebuggerTask(debugger_service=service)

    def _create_debugger_service(self):
        from .debugger_service import DebuggerService
        from ..twisted.ireactor import IReactorTCP

        # Get the twisted reactor from the reactor plugin
        self._debugger_service = service = DebuggerService(port=self.debug_port)

        reactor = self.application.get_service(IReactorTCP)
        reactor.listenTCP(self.debug_port, service)
        return service

