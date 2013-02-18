
import sys
from twisted.internet.protocol import ServerFactory
from plugins.debugger.debugger_protocol import PyToolsProtocol

class TestProtocol(PyToolsProtocol):
    def stringReceived(self, string):
        print string
        super(TestProtocol, self).stringReceived(string)

    def receive_LOAD(self, bytes):
        super(TestProtocol, self).receive_LOAD(bytes)
        self.send_DETC()

class DebugFactory(ServerFactory):
    def buildProtocol(self, addr):
        return TestProtocol(self)

    def processConnected(self, guid, protocol):
        pass

if __name__ == '__main__':
    from twisted.internet import reactor

    reactor.listenTCP(8000, DebugFactory())
    reactor.run()
