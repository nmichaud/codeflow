import uuid

# Enthought library imports
from traits.api import HasTraits, Bool, Instance, Dict, Int

# Local imports
from python_process import PythonProcess
from debugger_protocol import PyToolsProtocol
from twisted.internet.protocol import ServerFactory

class DebuggerService(HasTraits, ServerFactory):

    running = Bool(False)

    processes = Dict(uuid.UUID, PythonProcess)

    port = Int()

    def stop_service(self):
        for process in self.processes.values():
            process.Terminate()

    def debug(self):
        process = PythonProcess(port=self.port)
        # Add to internal cache before starting
        self.processes[process.ProcessGuid] = process
        return process

    def buildProtocol(self, addr):
        return PyToolsProtocol(self)

    def processConnected(self, guid, protocol):
        # Lookup the process and set up the protocol
        process = self.processes.get(uuid.UUID(guid))
        if process:
            process.protocol = protocol
