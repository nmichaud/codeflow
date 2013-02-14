from twisted.internet.protocol import Factory, Protocol
from twisted.internet.interfaces import IProtocol
from zope.interface import implements

# Enthought library imports
from traits.api import HasTraits, Any, Bool, Instance

# Local imports
from python_process import PythonProcess

class DebuggerService(HasTraits):

    reactor = Any()

    running = Bool(False)
    process = Instance(PythonProcess)

    def stop_service(self):
        if self.process:
            self.terminate()

    def listen(self, debug_port):
        self.reactor.listenTCP(debug_port, DebugFactory())

    def debug(self, filename):
        self.process = PythonProcess()
        self.process.Start(filename)

    def terminate(self):
        self.process.Terminate()

class DebugFactory(Factory):
    def __init__(self):
        self.numProtocols = 0

    def buildProtocol(self, addr):
        return PyToolsProtocol(self)

class PyToolsProtocol(Protocol):
    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        self.factory.numProtocols += 1
        self.transport.write(
            "Welcome! There are currently %d open connections.\n" %
               (self.factory.numProtocols,))

    def connectionLost(self, reason):
        self.factory.numProtocols -= 1

    def dataReceived(self, data):
        self.transport.write(data)

