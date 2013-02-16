# System imports
import os, sys, subprocess, uuid

# Enthought library imports
from traits.api import (
    HasTraits, Any, Event, Instance, Dict, List, Unicode, Bool, Int
    )

# Local imports
from debugger_protocol import PyToolsProtocol


class PythonProcess(HasTraits):

    _process = Instance(subprocess.Popen)
    _threads = Dict #(int, PythonThread)
    _breakpoints = Dict #(int, PythonBreakpoint)

    protocol = Instance(PyToolsProtocol)

    #_lineEvent
    #_ids = Instance(IdDispenser)
    #_pendingExecutes
    #_pendingChildEnums

    _processGuid = Instance(uuid.UUID)

    def __processGuid_default(self):
        return uuid.uuid4()

    _dirMapping = List(Unicode)

    _sentExited = Bool
    _breakpointCounter = Int
    _setLineResult = Bool
    _createdFirstThread = Bool
    _stoppedForException = Bool

    #_defaultBreakMode
    #_breakOn

    Id = property(lambda self: self._process.id)
    ProcessGuid = property(lambda self: self._processGuid)

    def Start(self, filename):
        # create process and start it
        exe = sys.executable

        args = [sys.executable,
                os.path.join(os.path.dirname(__file__), '..', '..', 'debuggee', 'visualstudio_py_launcher.py'),
                os.getcwd(),
                '8000',
                str(self._processGuid),
                filename,
                '--wait-on-exception',
                '--wait-on-exit',
                '--redirect-output',
                ]

        self._process = subprocess.Popen(args)
        # Wait for process to connect

    def WaitForExit(self):
        return self._process.wait()

    def Terminate(self):
        self._process.terminate()

    # API used by other pieces
    def SendStepInto(self, thread_id):
        self.protocol.send_STPI(thread_id)

    def SendStepOver(self, thread_id):
        self.protocol.send_STPV(thread_id)

    def SendStepOut(self, thread_id):
        self.protocol.send_STPO(thread_id)

    def SendResumeThread(self, thread_id):
        self.protocol.send_REST(thread_id)

    def SendClearStepping(self, thread_id):
        self.protocol.send_CLST(thread_id)

    def Resume(self):
        self.protocol.send_RESA()

    def Break(self):
        self.protocol.send_BRKA()

    def BindBreakPoint(self, breakpoint):
        self.protocol.send_BRKP(
            breakpoint.Id, breakpoint.LineNo, breakpoint.Filename,
            breakpoint.Condition, breakpoint.BreakWhenChanged
            )

    def RemoveBreakPoint(self, breakpoint):
        self._breakpoints.pop(breakpoint.Id)
        self.DisableBreakPoint(breakpoint)

    def DisableBreakPoint(self, breakpoint):
        self.protocol.send_BRKR(
            breakpoint.Id, breakpoint.LineNo
            )

    def SetBreakPointCondition(self, breakpoint):
        self.protocol.send_BRKC(
            breakpoint.Id, breakpoint.Condition,
            breakpoint.BreakWhenChanged
            )

    def SetLineNumber(self, frame, lineNo):
        self.protocol.send_SETL(
            frame.Thread.Id, frame.FrameId, LineNo
            )

    def ExecuteText(self, frame, completion):
        # XXX Create an execution id
        executionId = 0
        self.protocol.send_EXEC(
            completion, frame.Thread.Id, frame.FrameId,
            executionId)


class PythonEvaluationResult(HasTraits):
    pass


class PythonStackFrame(HasTraits):
    _lineNo = Int
    _frameName = Unicode
    _filename = Unicode
    _argCount = Int
    _frameId = Int
    _startLine = Int
    _endLine = Int

    _variables = List(Instance(PythonEvaluationResult))

    #_thread = Instance(PythonThread)

    StartLine = property(lambda self: self._startLine)
    EndLine = property(lambda self: self._endLine)
    Thread = property(lambda self: self._thread)
    LineNo = property(lambda self: self._lineNo, lambda self, val: self.trait_set(_lineNo=val))
    FunctionName = property(lambda self: self._frameName)
    FileName = property(lambda self: self._thread.Process.MapFile(self._filename, toDebuggee=False))
    FrameId = property(lambda self: self._frameId)
    def SetVariables(self, variables):
        self._variables = variables

    @property
    def Locals(self):
        return self._variables[self._argcount:]

    @property
    def Parameters(self):
        return self._variables[:self._argCount]

    def ExecuteText(self, text, completion):
        self._thread.Process.ExecuteText(text, self, completion)

    def SetLineNumber(self, lineNo):
        return self._thread.Process.SetLineNumber(self, lineNo)


class PythonThread(HasTraits):
    _identity = Int
    _process = Instance(PythonProcess)
    _isWorkerThread = Bool
    _name = Unicode
    _frames = List(Instance(PythonStackFrame))

    Process = property(lambda self: self._process)
    Name = property(lambda self: self._name, lambda self, val: self.trait_set(_name=val))
    Id = property(lambda self: self._identity)
    IsWorkerThread = property(lambda self: self._isWorkerThread)
    Frames = property(lambda self: self._frames, lambda self, val: self.trait_set(_frames, val))

    def StepInto(self):
        self._process.SendStepInto(self._identity)
    def StepOver(self):
        self._process.SendStepOver(self._identity)
    def StepOut(self):
        self._process.SendStepOut(self._identity)
    def Resume(self):
        self._process.SendResumeThread(self._identity)
    def ClearSteppingState(self):
        self._process.SendClearStepping(self._identity)


PythonStackFrame.add_class_trait('_thread', Instance(PythonThread))


class PythonBreakpoint(HasTraits):
    _process = Instance(PythonProcess)
    _filename = Unicode
    _lineNo = Int
    _breakpointId = Int
    _breakWhenChanged = Bool
    _condition = Unicode

    def Add(self):
        self._process.BindBreakPoint(self)

    def Remove(self):
        self._process.RemoveBreakPoint(self)

    def Disable(self):
        self._process.DisableBreakPoint(self)

    Filename = property(lambda self: self._filename)
    LineNo = property(lambda self: self._lineNo)
    Condition = property(lambda self: self._condition)
    Id = property(lambda self: self._breakpointId)
    BreakWhenChanged = property(lambda self: self._breakWhenChanged)

    def SetCondition(self, condition, breakWhenChanged):
        self._condition = condition
        self._breakWhenChanged = breakWhenChanged
        self._process.SetBreakPointCondition(self)

