# Enthought library imports
from traits.api import HasTraits, Any, Bool, Instance, Enum

# Local imports
from python_process import PythonProcess
from debugger_protocol import DebugFactory

class DebuggerService(HasTraits):

    reactor = Any()

    running = Bool(False)
    process = Instance(PythonProcess)

    server = Instance(DebugFactory, ())

    def stop_service(self):
        if self.process:
            self.terminate()

    def listen(self, debug_port):
        self.reactor.listenTCP(debug_port, self.server)

    def debug(self, filename):
        self.process = PythonProcess()
        self.process.Start(filename)

    def terminate(self):
        self.process.Terminate()
