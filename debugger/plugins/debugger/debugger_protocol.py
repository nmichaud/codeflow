import struct

from twisted.internet.interfaces import IProtocol
from twisted.protocols.basic import IntNStringReceiver
from zope.interface import implements

# Enthought library imports
from traits.api import HasTraits, Enum, Event

class PyToolsProtocol(HasTraits, IntNStringReceiver):

    implements(IProtocol)

    state = Enum('disconnected', ['disconnected', 'connected', 'debugging'])

    # Protocol events
    processLoaded = Event()
    processExited = Event()
    threadCreated = Event()
    threadExited = Event()
    stepComplete = Event()
    asyncBreakComplete = Event()
    moduleLoaded = Event()
    exceptionRaised = Event()
    breakpointHit = Event()
    breakpointBindSucceeded = Event()
    breakpointBindFailed = Event()
    setLineNoComplete = Event()
    debuggerOutput = Event()
    threadFrameList = Event()

    structFormat = "I"
    prefixLength = struct.calcsize(structFormat)

    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        self.state = 'connected'

    def connectionLost(self, reason):
        self.state = 'disconnected'

    def stringReceived(self, msg):
        # Unpack the msg
        code = msg[:4]
        # Dispatch code
        getattr(self, 'receive_%s'%code)(msg[4:])

    # Debugger commands to send
    # None of the commands sent to the debugger are length prefixed messages
    def send_STPI(self, thread_id):
        """ Step into command

        Data format:
        ------------
            thread id: long
        """
        self.transport.write('stpi')
        self.transport.write(struct.pack('l', thread_id))

    def send_STPO(self, thread_id):
        """ Step out command

        Data format:
        ------------
            thread id: long
        """
        self.transport.write('stpo')
        self.transport.write(struct.pack('l', thread_id))

    def send_STPV(self, thread_id):
        """ Step over command

        Data format:
        ------------
            thread id: long
        """
        self.transport.write('stpv')
        self.transport.write(struct.pack('l', thread_id))

    def send_BRKP(self, brkpt_id, line_no, filename, condition, break_when_changed):
        """ Set breakpoint command

        Data format:
        ------------
            breakpoint id: int
            line number: int
            filename: string
            condition: string
            break_when_changed: int
        """
        self.transport.write('brkp')
        self.transport.write(struct.pack('ii', brkpt_id, line_no))
        self._write_string(filename)
        self._write_string(condition)
        self.transport.write(struct.pack('i', 1 if break_when_changed else 0))

    def send_BRKC(self, brkpt_id, condition, break_when_changed):
        """ Set breakpoint with condition

        Data format:
            breakpoint id: int
            condition: string
            break_when_changed: int
        ------------
        """
        self.transport.write('brkc')
        self.transport.write(struct.pack('i', brkpt_id))
        self._write_string(condition)
        self.transport.write(struct.pack('i', 1 if break_when_changed else 0))

    def send_BRKR(self, brkpt_id, line_no):
        """ Remove breakpoint command

        Data format:
        ------------
            breakpoint id: int
            line number: int
        """
        self.transport.write('brkr')
        self.transport.write(struct.pack('ii', line_no, brkpt_id))

    def send_BRKA(self):
        """ Break all command

        Data format:
        ------------
        """
        self.transport.write('brka')

    def send_RESA(self):
        """ Resume all command

        Data format:
        ------------
        """
        self.transport.write('resa')

    def send_REST(self, thread_id):
        """ Resume thread command

        Data format:
        ------------
            thread id: long
        """
        self.transport.write('rest')
        self.transport.write(struct.pack('l', thread_id))

    def send_EXEC(self, code, thread_id, frame_id, execution_id):
        """ Execute code command

        Data format:
        ------------
            code: string
            thread id: long
            frame id: int
            execution id: int
            frame_kind: int  # UNUSED
        """
        self.transport.write('exec')
        self._write_string(code)
        self.transport.write(struct.pack('liii', thread_id, frame_id, execution_id, 1))

    def send_CHLD(self, code, thread_id, frame_id, execution_id, child_is_enumerate):
        """ Enumerate children in given frame

        Data format:
        -----------
            code: string
            thread_id: long
            frame_id: int
            execution_id: int
            frame_kind: int # UNUSED
            child_is_enumerate: int
        """
        self.transport.write('chld')
        self._write_string(code)
        self.transport.write(struct.pack('liiii', thread_id, frame_id, execution_id, 1, 1 if child_is_enumerate else 0))

    def send_SETL(self, thread_id, frame_id, line_number):
        """ Set line number command

        Data format:
        ------------
            thread id: long
            frame id: int
            line number: int
        """
        self.transport.write('setl')
        self.transport.write(struct.pack('lii', thread_id, frame_id, line_number))

    def send_DETC(self):
        """  Detach command

        Data format:
        -----------
        """
        self.transport.write('detc')

    def send_CLST(self, thread_id):
        """ Clear stepping command

        Data format:
        ------------
            thread id: long
        """
        self.transport.write('clst')
        self.transport.write(struct.pack('l', thread_id))

    def send_SEXI(self, exception_mode, exceptions):
        """ Set exception info command

        Data format:
        ------------
            break_mode: int
            exception count: int
            exceptions:
                mode: int
                name: string
        """
        self.transport.write('sexi')
        self.transport.write(struct.pack('ii', exception_mode, len(exceptions)))
        for excp in exceptions:
            self.transport.write(struct.pack('i', excp.mode))
            self._write_string(excp.name)

    def send_SEHI(self, statements):
        """ Set exception handler info command

        Data format:
        ------------
            filename: string
            statement count: int
            statements:
                line start: int
                line end: int
                text: string
        """
        # XXX The statement text format has to be worked out
        self.transport.write('sehi')
        self._write_string(filename)
        self.transport.write(struct.pack('i', len(statements)))
        for statement in statements:
            self.transport.write(struct.pack('ii', statement.start, statement.end))
            self._write_string(statement.text)

    def send_BKDR(self):
        """ Remove django breakpoint command

        Unsupported at this time
        """

    def send_BKDA(self):
        """ Add django breakpoint command

        Unsupported at this time
        """

    def send_CREP(self, port):
        """ Connect REPL command

        Data format:
        ------------
            port: int
        """
        self.transport.write('crep')
        self.transport.write(struct.pack('i', port))

    def send_DREP(self):
        """ Disconnect REPL command

        Data format:
        ------------
        """
        self.transport.write('drep')

    # Debugger events received
    def receive_CONN(self, bytes):
        """ Connected message

        Data format:
        -----------
            Debug ID: string
            Success flag: int
        """
        guid, bytes = self._read_string(bytes)
        flag, = struct.unpack('i', bytes)

        self.state = 'debugging'
        self.factory.processConnected(guid, self)

        # Send default exception handling info
        # format: count, (mode, name) - name is something like 'Exception.KeyError'
        # Mode is either BREAK_MODE_NEVER (0), BREAK_MODE_ALWAYS(1), BREAK_MODE_UNHANDLED(32)
        # XXX Ignore for now

    def receive_ASBR(self, bytes):
        """ Asynchronous break message

        Data format:
        ------------
            break id: int
        """
        brkpt_id, = struct.unpack('i', bytes)
        self.asyncBreakComplete = brkpt_id

    def receive_SETL(self, bytes):
        """ Set line number message

        Data format:
        ------------
            status: int
            thread id: long
            newline: int
        """
        status, thread_id, newline = struct.unpack('ili', bytes)
        self.setLineNoComplete = (status, thread_id, newline)

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
        thread_id, = struct.unpack('l', bytes[:8])
        tname, bytes = self._read_string(bytes[8:])
        fcount, = struct.unpack('i', bytes[:4])
        bytes = bytes[4:]
        frames = []
        for f_i in range(fcount):
            flineno,lineno,curlineno = struct.unpack('iii', bytes[:12])
            framename, bytes = self._read_string(bytes[12:])
            filename, bytes = self._read_string(bytes)
            argcount, vcount = struct.unpack('ii', bytes[:8])
            bytes = bytes[8:]
            vars = []
            for v_i in range(vcount):
                varname, bytes = self._read_string(bytes)
                obj, bytes = self._read_object(bytes)
                vars.append((varname, obj))
            frames.append((flineno,lineno,curlineno,framename,filename,argcount,vars))
        assert(len(bytes) == 0)
        self.threadFrameList = (thread_id, tname, frames)

    def receive_DETC(self, bytes):
        """ Detach message (process exited)

        Data format:
        ------------
            None
        """
        assert(len(bytes) == 0)
        self.processExited = True

    def receive_NEWT(self, bytes):
        """ New thread created

        Data format:
        -----------
            Thread ID: long
        """
        thread_id, = struct.unpack('l', bytes)
        self.threadCreated = thread_id

    def receive_EXTT(self, bytes):
        """ Thread exited message

        Data format:
        ------------
            thread id: long
        """
        thread_id, = struct.unpack('l', bytes)
        self.threadExited = thread_id

    def receive_EXCP(self, bytes):
        """ Exception reported message

        Data format:
        ------------
            name: string
            thread id: long
            break type: int
            exception text: string
        """
        name, bytes = self._read_string(bytes)
        thread_id, break_type = struct.unpack('li', bytes[:12])
        excp_text, bytes = self._read_string(bytes[12:])
        assert(len(bytes) == 0)
        self.exceptionRaised = (thread_id, name, break_type, excp_text)

    def receive_MODL(self, bytes):
        """ Module loaded message

        Data format:
        ------------
            Module id: long
            Module filename: string
        """
        module_id, = struct.unpack('l', bytes[:8])
        filename, bytes = self._read_string(bytes[8:])
        assert(len(bytes) == 0)
        self.moduleLoaded = (module_id, filename)

    def receive_STPD(self, bytes):
        """ Step done message

        Data format:
        ------------
            thread id: long
        """
        thread_id, = struct.unpack('l', bytes)
        self.stepComplete = True

    def receive_BRKS(self, bytes):
        """ Breakpoint set message

        Data format:
        ------------
            breakpoint id: int
        """
        brkpt_id, = struct.unpack('i', bytes)
        self.breakpointBindSucceeded = brkpt_id

    def receive_BRKF(self, bytes):
        """ Breakpoint failed message

        Data format:
        ------------
            breakpoint id: int
        """
        brkpt_id, = struct.unpack('i', bytes)
        self.breakpointBindFailed = brkpt_id

    def receive_BRKH(self, bytes):
        """ Breakpoint hit message

        Data format:
        ------------
            breakpoint id: int
            thread id: long
        """
        brkpt_id, thread_id = struct.unpack('il', bytes)
        self.breakpointHit = (thread_id, brkpt_id)

    def receive_LOAD(self, bytes):
        """ Process loaded message

        Data format:
        ------------
            thread id: long
        """
        thread_id, = struct.unpack('l', bytes)
        self.processLoaded = (thread_id,)

    def receive_EXCE(self, bytes):
        """ Execution error message

        Data format:
        ------------
            execution id: int
            exception text: string
        """
        eid, = struct.unpack('i', bytes[:4])
        string, bytes = self._read_string(bytes[4:])
        assert(len(bytes) == 0)

    def receive_EXCR(self, bytes):
        """ Execution result message

        Data format:
        ------------
            execution id: int
            result: object
        """
        eid, = struct.unpack('i', bytes[:4])
        obj, bytes = self._read_object(bytes[4:])
        assert(len(bytes) == 0)

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
        """ Process output message

        Data format:
        ------------
            thread id: long
            output: string
        """
        thread_id, = struct.unpack('l', bytes[:8])
        output, bytes = self._read_string(bytes[8:])
        assert(len(bytes) == 0)
        self.debuggerOutput = (thread_id, output)

    def receive_REQH(self, bytes):
        """ Request handler message

        Data format:
        ------------
            code_filename: string
        """
        fname, bytes = self._read_string(bytes)
        assert(len(bytes) == 0)

    def _write_string(self, string):
        """ Writes a string in the format expected by the debugger
        """
        # Use the protocol's sendString
        self.sendString(string.encode('utf8'))

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
