import struct

from twisted.internet.protocol import Factory
from twisted.internet.interfaces import IProtocol
from twisted.protocols.basic import IntNStringReceiver
from zope.interface import implements

# Enthought library imports
from traits.api import HasTraits, Any, Bool, Instance, Enum

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
    def buildProtocol(self, addr):
        return PyToolsProtocol(self)


class PyToolsProtocol(HasTraits, IntNStringReceiver):

    implements(IProtocol)

    state = Enum('disconnected', ['disconnected', 'connected', 'debugging'])
    structFormat = "I"
    prefixLength = struct.calcsize(structFormat)

    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        pass

    def connectionLost(self, reason):
        pass #print "connection lost", reason

    def stringReceived(self, msg):
        # Unpack the msg
        code = msg[:4]
        # Dispatch code
        getattr(self, 'receive_%s'%code)(msg[4:])

    # Debugger commands to send
    def send_STPI(self):
        " Step into"

    def send_STPO(self):
        " Step out"

    def send_STPV(self):
        " Step over"

    def send_BRKP(self):
        " Set breakpoint"

    def send_BRKC(self):
        " Set breakpoint with condition"

    def send_BRKR(self):
        " Remove breakpoint "

    def send_BRKA(self):
        " Break all "

    def send_RESA(self):
        " Resume all"

    def send_REST(self):
        " Resume thread"

    def send_EXEC(self):
        " Execute code"

    def send_CHLD(self):
        " Enumerate children"

    def send_SETL(self):
        " Set line number"

    def send_DETC(self):
        " Detach"

    def send_CLST(self):
        " Clear stepping"

    def send_SEXI(self):
        " Set exception info"

    def send_SEHI(self):
        " Set exception handler info"

    def send_BKDR(self):
        " Remove django breakpoint "

    def send_BKDA(self):
        " Add django breakpoint"

    def send_CREP(self):
        " Connect REPL"

    def send_DREP(self):
        " Disconnect REPL"

    # Debugger events received
    def receive_CONN(self, bytes):
        """ Connected message

        Data format:
        -----------
            Debug ID: string
            Success flag: int
        """
        string, bytes = self._read_string(bytes)
        flag, = struct.unpack('i', bytes)

        self.state = 'connected'

        # Send default exception handling info
        # format: count, (mode, name) - name is something like 'Exception.KeyError'
        # Mode is either BREAK_MODE_NEVER (0), BREAK_MODE_ALWAYS(1), BREAK_MODE_UNHANDLED(32)


    def receive_ASBR(self, bytes):
        " Async break"

    def receive_SETL(self, bytes):
        " Set line result"

    def receive_THRF(self, bytes):
        """ Thread frame list message

        Data format:
        ------------
            Thread ID: long
            Thread name: string
            Frame count: int
            Frame:
                First line number: int
                Line no: int
                Cur line no: int
                Name: string
                filename: string
                argcount: int
                num variables: int
                Variables:
                    name: string
                    Variable object:
                        repr: string
                        hex rep: string
                        type name: string
                        expandable: int
        """
        tid, = struct.unpack('l', bytes[:8])
        tname, bytes = self._read_string(bytes[8:])
        fcount, = struct.unpack('i', bytes[:4])
        print 'Thread:',tid, tname
        bytes = bytes[4:]
        for f_i in range(fcount):
            flineno,lineno,curlineno = struct.unpack('iii', bytes[:12])
            framename, bytes = self._read_string(bytes[12:])
            filename, bytes = self._read_string(bytes)
            argcount, vcount = struct.unpack('ii', bytes[:8])
            print '\tFrame', flineno, lineno, curlineno, framename, filename, argcount, vcount
            bytes = bytes[8:]
            for v_i in range(vcount):
                varname, bytes = self._read_string(bytes)
                obj, bytes = self._read_object(bytes)
                print '\t\tVar:', obj

        assert(len(bytes) == 0)

    def receive_DETC(self, bytes):
        " Detach - Process exited"

    def receive_NEWT(self, bytes):
        """ New thread created

        Data format:
        -----------
            Thread ID: long
        """
        tid, = struct.unpack('l', bytes)
        print tid

    def receive_EXTT(self, bytes):
        " Thread exited"

    def receive_EXIT(self, bytes):
        " not used"

    def receive_EXCP(self, bytes):
        " Exception"

    def receive_MODL(self, bytes):
        """ Module loaded message

        Data format:
        ------------
            Module id: long
            Module filename: string
        """
        mid, = struct.unpack('l', bytes[:8])
        filename, bytes = self._read_string(bytes[8:])
        print mid, filename
        assert(len(bytes) == 0)

    def receive_STPD(self, bytes):
        " Step done"

    def receive_BRKS(self, bytes):
        " Breakpoint set"

    def receive_BRKF(self, bytes):
        " Breakpoint failed"

    def receive_BRKH(self, bytes):
        " Breakpoint hit"

    def receive_LOAD(self, bytes):
        """ Process loaded message

        Data format:
        ------------
            thread id: long
        """
        tid, = struct.unpack('l', bytes)
        print "Thread loaded", tid

    def receive_EXCE(self, bytes):
        " Execution exception"

    def receive_EXCR(self, bytes):
        " Execution result"

    def receive_CHLD(self, bytes):
        """ Enumerate children

        Data format:
        ------------
            execution id: int
            num attributes: int
            num indices: int
            indices are index: int
            indices are enumarate: int
            Attribute Children:
                name: string
                object:
            Index children:
                name: string
                object:
        """
        eid, nattr, nidx, idx_are_index, idx_are_enum = struct.unpack('iiiii', bytes[:20])
        bytes = bytes[20:]
        for attr in range(nattr):
            name, bytes = self._read_string(bytes)
            obj, bytes = self._read_object(bytes)
        for idx in range(nidx):
            name, byptes = self._read_string(bytes)
            obj, bytes = self._read_object(bytes)

        assert(len(bytes) == 0)

    def receive_OUTP(self, bytes):
        " Process output"

    def receive_REQH(self, bytes):
        " Request Handler"


    def _read_string(self, bytes):
        """ Reads a string out of bytes, returning the string
            and any remaining bytes
        """
        # First character specifies a string code
        code = bytes[0]
        if code == 'N':
            return '', bytes[1:]
        else:
            size, = struct.unpack('i', bytes[1:5])
            string = bytes[5:5+size]
            if code == 'U':
                string = string.decode('utf8')
            return string, bytes[5+size:]

    def _read_object(self, bytes):
        """ Reads an object of out bytes, returning that object
            and any remaining bytes
        """
        varrepr, bytes = self._read_string(bytes)
        varhex, bytes = self._read_string(bytes)
        vartype, bytes = self._read_string(bytes)
        varexp, = struct.unpack('i', bytes[:4])
        bytes = bytes[4:]
        return (varrepr, varhex, vartype, varexp), bytes


def main():
    from twisted.internet import reactor

    reactor.listenTCP(8000, DebugFactory())
    reactor.run()

if __name__ == '__main__':
    main()
