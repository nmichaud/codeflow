# System imports
import os, sys, subprocess, uuid

# Enthought library imports
from traits.api import (
    HasTraits, Any, Event, Instance, Dict, List, Str, Bool, Int
    )


class PythonProcess(HasTraits):

    _process = Instance(subprocess.Popen)
    _threads = Dict #(int, PythonThread)
    _breakpoints = Dict #(int, PythonBreakpoint)

    #_lineEvent
    #_ids = Instance(IdDispenser)
    #_pendingExecutes
    #_pendingChildEnums

    #_langVersion

    _processGuid = Instance(uuid.UUID)

    def __processGuid_default(self):
        return uuid.uuid4()

    _dirMapping = List(Str)

    _delayUnregister = Bool

    _sentExited = Bool
    _socket = Any #Instance(Socket)
    _breakpointCounter = Int
    _setLineResult = Bool
    _createdFirstThread = Bool
    _stoppedForException = Bool

    #_defaultBreakMode
    #_breakOn

    Id = property(lambda self: self._process.id)
    ProcessGuid = property(lambda self: self._processGuid)

    def Start(self, filename, startListening=True):
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

        #self._process.Start()
        #if startListening:
        #    self.startListening()

    #def ListenForConnection(self):
    #    DebugConnectionListener.RegisterProcess(self._processGuid, self)

    #def __del__(self):
    #    DebugConnectionListener.UnregisterProcess(self._processGuid)

    def _process_Exited(self, sender, args):
        if not self._sentExited:
            self._sentExited = True
            exited = 1

    def WaitForExit(self):
        return self._process.wait()

    def Terminate(self):
        self._process.terminate()

    ProcessLoaded = Event
    ThreadCreated = Event
    ThreadExited = Event
    StepComplete = Event
    AsyncBreakComplete = Event
    ProcessExited = Event
    ModuleLoaded = Event
    ExceptionRaised = Event
    BreakpointHit = Event
    BreakpointBindSucceeded = Event
    BreakpointBindFailed = Event
    DebuggerOutput = Event

    # Debugger commands
    ExitCommandBytes = "exit"
    StepIntoCommandBytes = "stpi"
    StepOutCommandBytes = "stpo"
    StepOverCommandBytes = "stpv"
    BreakAllCommandBytes = "brka"
    SetBreakPointCommandBytes = "brkp"
    SetBreakPointConditionCommandBytes = "brkc"
    RemoveBreakPointCommandBytes = "brkr"
    ResumeAllCommandBytes = "resa"
    GetThreadFramesCommandBytes = "thrf"
    ExecuteTextCommandBytes = "exec"
    ResumeThreadCommandBytes = "rest"
    ClearSteppingCommandBytes = "clst"
    SetLineNumberCommand = "setl"
    GetChildrenCommandBytes = "chld"
    DetachCommandBytes = "detc"
    SetExceptionInfoCommandBytes = "sexi"
    SetExceptionHandlerInfoCommandBytes = "sehi"
    RemoveDjangoBreakPointCommandBytes = "bkdr"
    AddDjangoBreakPointCommandBytes = "bkda"
    ConnectReplCommandBytes = "crep"
    DisconnectReplCommandBytes = "drep"


class PythonEvaluationResult(HasTraits):
    pass

class PythonStackFrame(HasTraits):
    _lineNo = Int
    _frameName = Str
    _filename = Str
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
    _name = Str
    _frames = List(Instance(PythonStackFrame))

    Process = property(lambda self: self._process)
    Name = property(lambda self: self._name, lambda self, val: self.trait_set(_name=val))
    Id = property(lambda self: self._id)
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
    _filename = Str
    _lineNo = Int
    _breakpointId = Int
    _breakWhenChanged = Bool
    _condition = Str

    def Add(self):
        self._process.BindBreakpoint(self)

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

