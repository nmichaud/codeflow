 # ############################################################################
 #
 # Copyright (c) Microsoft Corporation. 
 #
 # This source code is subject to terms and conditions of the Apache License, Version 2.0. A 
 # copy of the license can be found in the License.html file at the root of this distribution. If 
 # you cannot locate the Apache License, Version 2.0, please send an email to 
 # vspython@microsoft.com. By using this source code in any fashion, you are agreeing to be bound 
 # by the terms of the Apache License, Version 2.0.
 #
 # You must not remove this notice, or any other, from this software.
 #
 # ###########################################################################

from __future__ import with_statement
import sys
import ctypes
try:
    import thread
except ImportError:
    import _thread as thread
import socket
import struct
import weakref
import traceback
import types
import bisect
try:
    import visualstudio_py_repl
except ImportError:
    # in the attach scenario, visualstudio_py_repl should already be defined
    visualstudio_py_repl
from os import path

try:
    xrange
except:
    xrange = range

if sys.platform == 'cli':
    import clr
    from System.Runtime.CompilerServices import ConditionalWeakTable
    IPY_SEEN_MODULES = ConditionalWeakTable[object, object]()

# save start_new_thread so we can call it later, we'll intercept others calls to it.

debugger_dll_handle = None
DETACHED = True
def thread_creator(func, args, kwargs = {}):
    id = _start_new_thread(new_thread_wrapper, (func, ) + args, kwargs)
        
    return id

_start_new_thread = thread.start_new_thread
THREADS = {}
THREADS_LOCK = thread.allocate_lock()
MODULES = []

BREAK_ON_SYSTEMEXIT_ZERO = False
DEBUG_STDLIB = False
DJANGO_DEBUG = False

# Py3k compat - alias unicode to str
try:
    unicode
except:
    unicode = str

# dictionary of line no to break point info
BREAKPOINTS = {}
DJANGO_BREAKPOINTS = {}

BREAK_WHEN_CHANGED_DUMMY = object()
# lock for calling .send on the socket
send_lock = thread.allocate_lock()

class _SendLockContextManager(object):
    """context manager for send lock.  Handles both acquiring/releasing the 
       send lock as well as detaching the debugger if the remote process 
       is disconnected"""

    def __enter__(self):
        send_lock.acquire()

    def __exit__(self, exc_type, exc_value, tb):        
        send_lock.release()
        
        if exc_type is not None:
            print(exc_value)
            traceback.print_tb(tb)
            detach_threads()
            
            detach_process()

            # swallow the exception, we're no longer debugging
            return True 
        

_SendLockCtx = _SendLockContextManager()


class _NetstringWrapper(object):
    def __init__(self, conn=None):
        self._data = []
        self._conn = conn

    def send(self, data):
        # Accumulate the data to send
        self._data.append(data)

    def __enter__(self):
        # Buffer all sends through this object
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        global conn
        if self._conn:
            _c = self._conn
        else:
            _c = conn
        if exc_type is None and self._data:
            data, self._data = ''.join(self._data), []
            _c.send(struct.pack('!I', len(data)))
            _c.send(data)
        return False

_NetstringConn = _NetstringWrapper()

class _Getch(object):
    """Gets a single character from standard input.  Does not echo to the
screen."""
    def __init__(self):
        try:
            import msvcrt
            self._impl = msvcrt.getch
        except ImportError:
            self._impl = self._unix_getch

    def _unix_getch(self):
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def __call__(self): return self._impl()

getch = _Getch()


SEND_BREAK_COMPLETE = False

STEPPING_OUT = -1  # first value, we decrement below this
STEPPING_NONE = 0
STEPPING_BREAK = 1
STEPPING_LAUNCH_BREAK = 2
STEPPING_ATTACH_BREAK = 3
STEPPING_INTO = 4
STEPPING_OVER = 5     # last value, we increment past this.

USER_STEPPING = (STEPPING_OUT, STEPPING_INTO, STEPPING_OVER)

FRAME_KIND_NONE = 0
FRAME_KIND_PYTHON = 1
FRAME_KIND_DJANGO = 2

def cmd(cmd_str):
    if sys.version >= '3.0':
        return bytes(cmd_str, 'ascii')
    return cmd_str

if sys.version[0] == '3':
  # work around a crashing bug on CPython 3.x where they take a hard stack overflow
  # we'll never see this exception but it'll allow us to keep our try/except handler
  # the same across all versions of Python
  class StackOverflowException(Exception): pass
else:
  StackOverflowException = RuntimeError
  
# we can't run the importer at some random point because we might be importing 
# something complete with the loader lock held.  Therefore we eagerly run a UTF8
# decode here so that any required imports for it to succeed later have already
# been imported.

cmd('').decode('utf8')
''.encode('utf8') # just in case they differ in what they import...

CONN = cmd('CONN')
ASBR = cmd('ASBR')
SETL = cmd('SETL')
THRF = cmd('THRF')
DETC = cmd('DETC')
NEWT = cmd('NEWT')
EXTT = cmd('EXTT')
EXIT = cmd('EXIT')
EXCP = cmd('EXCP')
MODL = cmd('MODL')
STPD = cmd('STPD')
BRKS = cmd('BRKS')
BRKF = cmd('BRKF')
BRKH = cmd('BRKH')
LOAD = cmd('LOAD')
EXCE = cmd('EXCE')
EXCR = cmd('EXCR')
CHLD = cmd('CHLD')
OUTP = cmd('OUTP')
REQH = cmd('REQH')
UNICODE_PREFIX = cmd('U')
ASCII_PREFIX = cmd('A')
NONE_PREFIX = cmd('N')

def get_thread_from_id(id):
    THREADS_LOCK.acquire()
    try:
        return THREADS.get(id)
    finally:
        THREADS_LOCK.release()

def should_send_frame(frame):
    return frame is not None and frame.f_code not in (get_code(debug), get_code(execfile), get_code(new_thread_wrapper))

def lookup_builtin(name, frame):
    try:
        return  frame.f_builtins.get(bits)
    except:
        # http://ironpython.codeplex.com/workitem/30908
        builtins = frame.f_globals['__builtins__']
        if not isinstance(builtins, dict):
            builtins = builtins.__dict__
        return builtins.get(name)

def lookup_local(frame, name):
    bits = name.split('.')
    obj = frame.f_locals.get(bits[0]) or frame.f_globals.get(bits[0]) or lookup_builtin(bits[0], frame)
    bits.pop(0)
    while bits and obj is not None and type(obj) is types.ModuleType:
        obj = getattr(obj, bits.pop(0), None)
    return obj
        
# These constants come from Visual Studio - enum_EXCEPTION_STATE
BREAK_MODE_NEVER = 0
BREAK_MODE_ALWAYS = 1
BREAK_MODE_UNHANDLED = 32

BREAK_TYPE_NONE = 0
BREAK_TYPE_UNHANLDED = 1
BREAK_TYPE_HANDLED = 2

class ExceptionBreakInfo(object):
    BUILT_IN_HANDLERS = {
        '<frozen importlib._bootstrap>': ((None, None, '*'),)
    }

    def __init__(self):
        self.default_mode = BREAK_MODE_UNHANDLED
        self.break_on = { }
        self.handler_cache = dict(self.BUILT_IN_HANDLERS)
        self.handler_lock = thread.allocate_lock()
        self.AddException('exceptions.IndexError', BREAK_MODE_NEVER)
        self.AddException('exceptions.KeyError', BREAK_MODE_NEVER)
        self.AddException('exceptions.AttributeError', BREAK_MODE_NEVER)
        self.AddException('exceptions.StopIteration', BREAK_MODE_NEVER)
        self.AddException('exceptions.GeneratorExit', BREAK_MODE_NEVER)

    def Clear(self):
        self.default_mode = BREAK_MODE_UNHANDLED
        self.break_on.clear()
        self.handler_cache = dict(self.BUILT_IN_HANDLERS)

    def ShouldBreak(self, thread, ex_type, ex_value, trace):
        probe_stack()
        name = ex_type.__module__ + '.' + ex_type.__name__
        mode = self.break_on.get(name, self.default_mode)
        break_type = BREAK_TYPE_NONE
        if mode & BREAK_MODE_ALWAYS:
            if self.IsHandled(thread, ex_type, ex_value, trace):
                break_type = BREAK_TYPE_HANDLED
            else:
                break_type = BREAK_TYPE_UNHANLDED
        elif (mode & BREAK_MODE_UNHANDLED) and not self.IsHandled(thread, ex_type, ex_value, trace):
            break_type = BREAK_TYPE_HANDLED

        if break_type:
            if issubclass(ex_type, SystemExit):
                if not BREAK_ON_SYSTEMEXIT_ZERO:
                    if ((isinstance(ex_value, int) and not ex_value) or 
                        (isinstance(ex_value, SystemExit) and not ex_value.code)):
                        break_type = BREAK_TYPE_NONE

        return break_type
    
    def IsHandled(self, thread, ex_type, ex_value, trace):
        if trace is None:
            # get out if we didn't get a traceback
            return False

        if trace.tb_next is not None:
            # don't break if this isn't the top of the traceback
            return True
            
        cur_frame = trace.tb_frame
        
        while should_send_frame(cur_frame) and cur_frame.f_code.co_filename is not None:
            if not is_same_py_file(cur_frame.f_code.co_filename, __file__):
                handlers = self.handler_cache.get(cur_frame.f_code.co_filename)
            
                if handlers is None:
                    # req handlers for this file from the debug engine
                    self.handler_lock.acquire()
                
                    with _SendLockCtx, _NetstringConn as conn:
                        conn.send(REQH)
                        write_string(conn,cur_frame.f_code.co_filename)

                    # wait for the handler data to be received
                    self.handler_lock.acquire()
                    self.handler_lock.release()

                    handlers = self.handler_cache.get(cur_frame.f_code.co_filename)

                if handlers is None:
                    # no code available, so assume unhandled
                    return False

                line = cur_frame.f_lineno
                for line_start, line_end, expressions in handlers:
                    if line_start is None or line_start <= line < line_end:
                        if '*' in expressions:
                            return True

                        for text in expressions:
                            try:
                                res = lookup_local(cur_frame, text)
                                if res is not None and issubclass(ex_type, res):
                                    return True
                            except:
                                pass

            cur_frame = cur_frame.f_back

        return False
    
    def AddException(self, name, mode=BREAK_MODE_UNHANDLED):
        if sys.version_info[0] >= 3 and name.startswith('exceptions.'):
            name = 'builtins' + name[10:]
        
        self.break_on[name] = mode

BREAK_ON = ExceptionBreakInfo()

def probe_stack(depth = 10):
  """helper to make sure we have enough stack space to proceed w/o corrupting 
     debugger state."""
  if depth == 0:
      return
  probe_stack(depth - 1)


# specifies list of files not to debug, can be added to externally (the REPL does this
# for $attach support and not stepping into the REPL)
 
DONT_DEBUG = [__file__]
def should_debug_code(code):
    if not DEBUG_STDLIB and code.co_filename.startswith(sys.prefix):
        return False

    filename = code.co_filename
    for dont_debug_file in DONT_DEBUG:
        if is_same_py_file(filename, dont_debug_file):
            return False

    return True

attach_lock = thread.allocate()
attach_sent_break = False


def filename_is_same(filename1, filename2):
    if path.isabs(filename1) and path.isabs(filename2):
        return path.normcase(filename1) == path.normcase(filename2)
    return path.normcase(path.basename(filename1)) == path.normcase(path.basename(filename2))


def update_all_thread_stacks(blocking_thread):
    THREADS_LOCK.acquire()
    all_threads = list(THREADS.values())
    THREADS_LOCK.release()
    
    for cur_thread in all_threads:
        if cur_thread is blocking_thread:
            continue
            
        cur_thread._block_starting_lock.acquire()
        if not cur_thread._is_blocked:
            # release the lock, we're going to run user code to evaluate the frames
            cur_thread._block_starting_lock.release()        
                            
            frames = cur_thread.get_frame_list()
    
            # re-acquire the lock and make sure we're still not blocked.  If so send
            # the frame list.
            cur_thread._block_starting_lock.acquire()
            if not cur_thread._is_blocked:
                cur_thread.send_frame_list(frames)
    
        cur_thread._block_starting_lock.release()


class DjangoBreakpointInfo(object):
    def __init__(self, filename):
        self._line_locations = None
        self.filename = filename
        self.breakpoints = {}
    
    def add_breakpoint(self, lineno, brkpt_id):
        self.breakpoints[lineno] = brkpt_id

    def remove_breakpoint(self, lineno):
        del self.breakpoints[lineno]
    
    @property
    def line_locations(self):
        if self._line_locations is None:
            # we need to calculate our line number offset information
            try:
                contents = file(self.filename, 'r')
                line_info = []
                file_len = 0
                for line in contents:
                    if not line_info and line.startswith('\xef\xbb\xbf'):
                        line = line[3:] # Strip the BOM, Django seems to ignore this...
                    file_len += len(line)
                    line_info.append(file_len)
                contents.close()
                self._line_locations = line_info
            except:
                # file not available, locked, etc...
                pass

        return self._line_locations

    def get_line_range(self, start, end):
        line_locs = self.line_locations 
        if line_locs is not None:
            low_line = bisect.bisect_right(line_locs, start)
            hi_line = bisect.bisect_right(line_locs, end)

            return low_line, hi_line

        return (None, None)

    def should_break(self, start, end):
        low_line, hi_line = self.get_line_range(start, end)
        if low_line is not None and hi_line is not None:
            # low_line/hi_line is 0 based, self.breakpoints is 1 based
            for i in xrange(low_line+1, hi_line+2): 
                bkpt_id = self.breakpoints.get(i)
                if bkpt_id  is not None:
                    return True, bkpt_id 

        return False, 0


def get_django_frame_source(frame):
    if frame.f_code.co_name == 'render':
        self_obj = frame.f_locals.get('self', None)
        if self_obj is not None and type(self_obj).__name__ != 'TextNode':
            source_obj = getattr(self_obj, 'source', None)
            if source_obj is not None:
                return source_obj

    return None

class ModuleExitFrame(object):
    def __init__(self, real_frame):
        self.real_frame = real_frame
        self.f_lineno = real_frame.f_lineno + 1

    def __getattr__(self, name):
        return getattr(self.real_frame, name)

class Thread(object):
    def __init__(self, id = None):
        if id is not None:
            self.id = id 
        else:
            self.id = thread.get_ident()
        self._events = {'call' : self.handle_call, 
                        'line' : self.handle_line, 
                        'return' : self.handle_return, 
                        'exception' : self.handle_exception,
                        'c_call' : self.handle_c_call,
                        'c_return' : self.handle_c_return,
                        'c_exception' : self.handle_c_exception,
                       }
        self.cur_frame = None
        self.stepping = STEPPING_NONE
        self.unblock_work = None
        self._block_lock = thread.allocate_lock()
        self._block_lock.acquire()
        self._block_starting_lock = thread.allocate_lock()
        self._is_blocked = False
        self._is_working = False
        self.stopped_on_line = None
        self.detach = False
        self.trace_func = self.trace_func # replace self.trace_func w/ a bound method so we don't need to re-create these regularly
        self.prev_trace_func = None
        self.trace_func_stack = []
        self.reported_process_loaded = False
        self.django_stepping = None
        if sys.platform == 'cli':
            self.frames = []
    
    if sys.platform == 'cli':
        # workaround an IronPython bug where we're sometimes missing the back frames
        # http://ironpython.codeplex.com/workitem/31437
        def push_frame(self, frame):
            self.cur_frame = frame
            self.frames.append(frame)

        def pop_frame(self):
            self.frames.pop()
            self.cur_frame = self.frames[-1]
    else:
        def push_frame(self, frame):
            self.cur_frame = frame

        def pop_frame(self):
            self.cur_frame = self.cur_frame.f_back


    def trace_func(self, frame, event, arg):
        try:
            if self.stepping == STEPPING_BREAK and should_debug_code(frame.f_code):
                if self.cur_frame is None:
                    # happens during attach, we need frame for blocking
                    self.push_frame(frame)

                if self.detach:
                    sys.settrace(None)
                    return None

                self.async_break()

            return self._events[event](frame, arg)
        except (StackOverflowException, KeyboardInterrupt):
            # stack overflow, disable tracing
            return self.trace_func
    
    def handle_call(self, frame, arg):
        self.push_frame(frame)

        if DJANGO_BREAKPOINTS:
            source_obj = get_django_frame_source(frame)
            if source_obj is not None:
                origin, (start, end) = source_obj
                    
                active_bps = DJANGO_BREAKPOINTS.get(origin.name.lower())
                should_break = False
                if active_bps is not None:
                    should_break, bkpt_id = active_bps.should_break(start, end)
                    if should_break:
                        probe_stack()
                        update_all_thread_stacks(self)
                        self.block(lambda: (report_breakpoint_hit(bkpt_id, self.id), mark_all_threads_for_break()))
                if not should_break and self.django_stepping:
                    self.django_stepping = None
                    self.stepping = STEPPING_OVER
                    self.block_maybe_attach()

        if frame.f_code.co_name == '<module>' and frame.f_code.co_filename != '<string>':
            probe_stack()
            code, module = new_module(frame)
            if not DETACHED:
                report_module_load(module)

                # see if this module causes new break points to be bound
                bound = set()
                global PENDING_BREAKPOINTS
                for pending_bp in PENDING_BREAKPOINTS:
                    if check_break_point(code.co_filename, module, pending_bp.brkpt_id, pending_bp.lineNo, pending_bp.filename, pending_bp.condition, pending_bp.break_when_changed):
                        bound.add(pending_bp)
                PENDING_BREAKPOINTS -= bound

        stepping = self.stepping
        if stepping is not STEPPING_NONE:
            if stepping == STEPPING_INTO:
                # block when we hit the 1st line, not when we're on the function def
                self.stepping = STEPPING_OVER
                # empty stopped_on_line so that we will break even if it is
                # the same line
                self.stopped_on_line = None            
            elif stepping >= STEPPING_OVER:
                self.stepping += 1
            elif stepping <= STEPPING_OUT:
                self.stepping -= 1

        if (sys.platform == 'cli' and 
            frame.f_code.co_name == '<module>' and 
            not IPY_SEEN_MODULES.TryGetValue(frame.f_code)[0]):
            IPY_SEEN_MODULES.Add(frame.f_code, None)
            # work around IronPython bug - http://ironpython.codeplex.com/workitem/30127
            self.handle_line(frame, arg)

        # forward call to previous trace function, if any, saving old trace func for when we return
        old_trace_func = self.prev_trace_func
        if old_trace_func is not None:
            self.trace_func_stack.append(old_trace_func)
            self.prev_trace_func = None  # clear first incase old_trace_func stack overflows
            self.prev_trace_func = old_trace_func(frame, 'call', arg)

        return self.trace_func
        
    def handle_line(self, frame, arg):
        if not DETACHED:
            stepping = self.stepping

            # http://pytools.codeplex.com/workitem/815
            # if we block for a step into/over we don't want to block again for a breakpoint
            blocked_for_stepping = False

            if stepping is not STEPPING_NONE:   # check for the common case of no stepping first...
                if (((stepping == STEPPING_OVER or stepping == STEPPING_INTO) and frame.f_lineno != self.stopped_on_line) 
                    or stepping == STEPPING_LAUNCH_BREAK 
                    or stepping == STEPPING_ATTACH_BREAK):
                    if ((stepping == STEPPING_LAUNCH_BREAK and not MODULES) or                        
                        not should_debug_code(frame.f_code)):  # don't break into our own debugger / non-user code
                        # don't break into inital Python code needed to set things up
                        return self.trace_func
                    
                    blocked_for_stepping = stepping != STEPPING_LAUNCH_BREAK and stepping != STEPPING_ATTACH_BREAK
                    self.block_maybe_attach()

            if BREAKPOINTS and blocked_for_stepping is False:
                bp = BREAKPOINTS.get(frame.f_lineno)
                if bp is not None:
                    for (filename, bp_id), (condition, bound) in bp.items():
                        if filename == frame.f_code.co_filename or (not bound and filename_is_same(filename, frame.f_code.co_filename)):   
                            if condition:                            
                                try:
                                    res = eval(condition.condition, frame.f_globals, frame.f_locals)
                                    if condition.break_when_changed:
                                        block = condition.last_value != res
                                        condition.last_value = res
                                    else:
                                        block = res
                                except:
                                    block = True
                            else:
                                block = True

                            if block:
                                probe_stack()
                                update_all_thread_stacks(self)
                                self.block(lambda: (report_breakpoint_hit(bp_id, self.id), mark_all_threads_for_break()))
                            break

        # forward call to previous trace function, if any, updating trace function appropriately
        old_trace_func = self.prev_trace_func
        if old_trace_func is not None:
            self.prev_trace_func = None  # clear first incase old_trace_func stack overflows
            self.prev_trace_func = old_trace_func(frame, 'line', arg)

        return self.trace_func
    
    def handle_return(self, frame, arg):
        self.pop_frame()

        if not DETACHED:
            stepping = self.stepping
            if stepping is not STEPPING_NONE:
                if stepping > STEPPING_OVER:
                    self.stepping -= 1
                elif stepping < STEPPING_OUT:
                    self.stepping += 1
                elif stepping in USER_STEPPING and should_debug_code(frame.f_code):
                    if self.cur_frame is None or frame.f_code.co_name == "<module>" :
                        # restore back the module frame for the step out of a module
                        self.push_frame(ModuleExitFrame(frame))
                        self.stepping = STEPPING_NONE
                        update_all_thread_stacks(self)
                        self.block(lambda: report_step_finished(self.id))
                        self.pop_frame()
                    else:
                        self.stepping = STEPPING_NONE
                        update_all_thread_stacks(self)
                        self.block(lambda: report_step_finished(self.id))

        # forward call to previous trace function, if any
        old_trace_func = self.prev_trace_func
        if old_trace_func is not None:
            old_trace_func(frame, 'return', arg)

        # restore previous frames trace function if there is one
        if self.trace_func_stack:
            self.prev_trace_func = self.trace_func_stack.pop()
        
    def handle_exception(self, frame, arg):
        if self.stepping == STEPPING_ATTACH_BREAK:
            self.block_maybe_attach()

        if not DETACHED and should_debug_code(frame.f_code):
            break_type = BREAK_ON.ShouldBreak(self, *arg)
            if break_type:
                update_all_thread_stacks(self)
                self.block(lambda: report_exception(frame, arg, self.id, break_type))

        # forward call to previous trace function, if any, updating the current trace function
        # with a new one if available
        old_trace_func = self.prev_trace_func
        if old_trace_func is not None:
            self.prev_trace_func = old_trace_func(frame, 'exception', arg)

        return self.trace_func
        
    def handle_c_call(self, frame, arg):
        # break points?
        pass
        
    def handle_c_return(self, frame, arg):
        # step out of ?
        pass
        
    def handle_c_exception(self, frame, arg):
        pass

    def block_maybe_attach(self):
        will_block_now = True
        if self.stepping == STEPPING_ATTACH_BREAK:
            # only one thread should send the attach break in
            attach_lock.acquire()
            global attach_sent_break
            if attach_sent_break:
                will_block_now = False
            attach_sent_break = True
            attach_lock.release()
    
        probe_stack()
        stepping = self.stepping
        self.stepping = STEPPING_NONE
        def block_cond():
            if will_block_now:
                if stepping == STEPPING_OVER or stepping == STEPPING_INTO:
                    return report_step_finished(self.id)
                else:
                    if stepping == STEPPING_ATTACH_BREAK:
                        self.reported_process_loaded = True
                    return report_process_loaded(self.id)
        update_all_thread_stacks(self)
        self.block(block_cond)
    
    def async_break(self):
        def async_break_send():
            with _SendLockCtx, _NetstringConn as conn:
                sent_break_complete = False
                global SEND_BREAK_COMPLETE
                if SEND_BREAK_COMPLETE:
                    # multiple threads could be sending this...
                    SEND_BREAK_COMPLETE = False
                    sent_break_complete = True
                    conn.send(ASBR)
                    conn.send(struct.pack('!Q', self.id))

            if sent_break_complete:
                # if we have threads which have not broken yet capture their frame list and 
                # send it now.  If they block we'll send an updated (and possibly more accurate - if
                # there are any thread locals) list of frames.
                update_all_thread_stacks(self)

        self.stepping = STEPPING_NONE
        self.block(async_break_send)

    def block(self, block_lambda):
        """blocks the current thread until the debugger resumes it"""
        assert not self._is_blocked
        #assert self.id == thread.get_ident(), 'wrong thread identity' + str(self.id) + ' ' + str(thread.get_ident())    # we should only ever block ourselves
        
        # send thread frames before we block
        self.enum_thread_frames_locally()
        
        self.stopped_on_line = self.cur_frame.f_lineno
        # need to synchronize w/ sending the reason we're blocking
        self._block_starting_lock.acquire()
        self._is_blocked = True
        block_lambda()
        self._block_starting_lock.release()

        while not DETACHED:
            self._block_lock.acquire()
            if self.unblock_work is None:
                break

            # the debugger wants us to do something, do it, and then block again
            self._is_working = True
            self.unblock_work()
            self.unblock_work = None
            self._is_working = False
                
        self._block_starting_lock.acquire()
        assert self._is_blocked
        self._is_blocked = False
        self._block_starting_lock.release()

    def unblock(self):
        """unblocks the current thread allowing it to continue to run"""
        assert self._is_blocked 
        assert self.id != thread.get_ident()    # only someone else should unblock us
        
        self._block_lock.release()

    def schedule_work(self, work):
        self.unblock_work = work
        self.unblock()

    def run_on_thread(self, text, cur_frame, execution_id, frame_kind):
        self._block_starting_lock.acquire()
        
        if not self._is_blocked:
            report_execution_error('<expression cannot be evaluated at this time>', execution_id)
        elif not self._is_working:
            self.schedule_work(lambda : self.run_locally(text, cur_frame, execution_id, frame_kind))
        else:
            report_execution_error('<error: previous evaluation has not completed>', execution_id)
        
        self._block_starting_lock.release()

    def run_on_thread_no_report(self, text, cur_frame, frame_kind):
        self._block_starting_lock.acquire()
        
        if not self._is_blocked:
            pass
        elif not self._is_working:
            self.schedule_work(lambda : self.run_locally_no_report(text, cur_frame, frame_kind))
        else:
            pass
        
        self._block_starting_lock.release()

    def enum_child_on_thread(self, text, cur_frame, execution_id, child_is_enumerate, frame_kind):
        self._block_starting_lock.acquire()
        if not self._is_working and self._is_blocked:
            self.schedule_work(lambda : self.enum_child_locally(text, cur_frame, execution_id, child_is_enumerate, frame_kind))
            self._block_starting_lock.release()
        else:
            self._block_starting_lock.release()
            report_children(execution_id, [], [], False, False)

    def get_locals(self, cur_frame, frame_kind):
        if frame_kind == FRAME_KIND_DJANGO:
            locs = {}
            # iterate going forward, so later items replace earlier items
            for d in cur_frame.f_locals['context'].dicts:
                # hasattr check to defend against someone passing a bad dictionary value
                # and us breaking the app.
                if hasattr(d, 'keys'):
                    for key in d.keys():
                        locs[key] = d[key]
        else:
            locs = cur_frame.f_locals
        return locs

    def locals_to_fast(self, frame):
        try:
            ltf = ctypes.pythonapi.PyFrame_LocalsToFast
            ltf.argtypes = [ctypes.py_object, ctypes.c_int]
            ltf(frame, 1)
        except:
            pass

    def compile(self, text, cur_frame):
        try:
            code = compile(text, '<debug input>', 'eval')
        except:
            code = compile(text, '<debug input>', 'exec')
        return code

    def run_locally(self, text, cur_frame, execution_id, frame_kind):
        try:
            code = self.compile(text, cur_frame)
            res = eval(code, cur_frame.f_globals, self.get_locals(cur_frame, frame_kind))
            self.locals_to_fast(cur_frame)
            report_execution_result(execution_id, res)
        except:
            report_execution_exception(execution_id, sys.exc_info())

    def run_locally_no_report(self, text, cur_frame, frame_kind):
        code = self.compile(text, cur_frame)
        res = eval(code, cur_frame.f_globals, self.get_locals(cur_frame, frame_kind))
        self.locals_to_fast(cur_frame)
        sys.displayhook(res)

    def enum_child_locally(self, text, cur_frame, execution_id, child_is_enumerate, frame_kind):
        def get_attributes(res):
            items = []
            for name in dir(res):
                if not (name.startswith('__') and name.endswith('__')):
                    try:
                        item = getattr(res, name)
                        if not hasattr(item, '__call__'):
                            items.append( (name, item) )
                    except:
                        # skip this item if we can't display it...
                        pass
            return items

        try:
            if child_is_enumerate:
                # remove index from eval, then get the index back.
                index_size = 0
                enumerate_index = 0
                for c in reversed(text):
                    index_size += 1
                    if c.isdigit():
                        enumerate_index = enumerate_index * 10 + (ord(c) - ord('0'))
                    elif c == '[':
                        text = text[:-index_size]
                        break
            
            code = compile(text, cur_frame.f_code.co_name, 'eval')
            res = eval(code, cur_frame.f_globals, self.get_locals(cur_frame, frame_kind))
            
            if child_is_enumerate:
                for index, value in enumerate(res):
                    if enumerate_index == index:
                        res = value
                        break
                else:
                    # value changed?
                    report_children(execution_id, [], [], False, False)
                    return
            
            indices_are_index = False
            indices_are_enumerate = False
            maybe_enumerate = False
            try:
                if isinstance(res, types.GeneratorType):
                    # go to the except block
                    raise Exception('generator')
                elif isinstance(res, dict) or (hasattr(res, 'items') and hasattr(res, 'has_key')):
                    # dictionary-like object
                    enum = res.items()
                else:
                    # indexable object
                    enum = enumerate(res)
                    maybe_enumerate = True

                indices = []
                for index, item in enum:
                    try:
                        if len(indices) > 10000:
                            # report at most 10000 items.
                            indices.append( ('[...]', 'Evaluation halted because sequence included too many items...') )
                            break
                        
                        indices.append( ('[' + repr(index) + ']', item) )
                        if maybe_enumerate and not indices_are_enumerate:
                            # check if we can index back into this object, or if we have to use
                            # enumerate to get values out of it.
                            try:
                                fetched = res[index]
                                if fetched is not item:
                                    indices_are_enumerate = True
                            except:
                                indices_are_enumerate = True
                                
                    except:
                        # ignore bad objects for now...
                        pass

                indices_are_index = True
            except:
                # non-indexable object
                indices = []

            report_children(execution_id, get_attributes(res), indices, indices_are_index, indices_are_enumerate)
        except:
            report_children(execution_id, [], [], False, False)

    def get_frame_list(self):
        frames = []
        cur_frame = self.cur_frame
        
        while should_send_frame(cur_frame):
            # calculate the ending line number
            lineno = cur_frame.f_code.co_firstlineno
            try:
                linetable = cur_frame.f_code.co_lnotab
            except:
                try:
                    lineno = cur_frame.f_code.Span.End.Line
                except:
                    lineno = -1
            else:
                for line_incr in linetable[1::2]:
                    if sys.version >= '3':
                        lineno += line_incr
                    else:
                        lineno += ord(line_incr)

            source_obj = None
            frame_locals = cur_frame.f_locals
            if DJANGO_DEBUG:
                source_obj = get_django_frame_source(cur_frame)
                if source_obj is not None:
                    frame_locals = self.get_locals(cur_frame, FRAME_KIND_DJANGO)

            if source_obj is not None:
                var_names = frame_locals
            elif frame_locals is cur_frame.f_globals:
                var_names = cur_frame.f_globals
            else:
                var_names = cur_frame.f_code.co_varnames
                        
            vars = []
            for var_name in var_names:
                try:
                    obj = frame_locals[var_name]
                except:
                    obj = '<undefined>'
                try:
                    if sys.version[0] == '2' and type(obj) is types.InstanceType:
                        type_name = "instance (" + obj.__class__.__name__ + ")"
                    else:
                        type_name = type(obj).__name__
                except:
                    type_name = 'unknown'
                    
                vars.append((var_name, type(obj), safe_repr(obj), safe_hex_repr(obj), type_name, get_object_len(obj)))
                
        
            frame_info = None

            if source_obj is not None:
                origin, (start, end) = source_obj

                filename = str(origin)
                bp_info = DJANGO_BREAKPOINTS.get(filename.lower())
                if bp_info is None:
                    DJANGO_BREAKPOINTS[filename.lower()] = bp_info = DjangoBreakpointInfo(filename)

                low_line, hi_line = bp_info.get_line_range(start, end)
                if low_line is not None and hi_line is not None:
                    frame_kind = FRAME_KIND_DJANGO
                    frame_info = (
                        low_line + 1,
                        hi_line + 1, 
                        low_line + 1, 
                        cur_frame.f_code.co_name,
                        str(origin),
                        0,
                        vars,
                        FRAME_KIND_DJANGO,
                        get_code_filename(cur_frame.f_code),
                        cur_frame.f_lineno
                    )

            if frame_info is None:
                frame_info = (
                    cur_frame.f_code.co_firstlineno,
                    lineno, 
                    cur_frame.f_lineno, 
                    cur_frame.f_code.co_name,
                    get_code_filename(cur_frame.f_code),
                    cur_frame.f_code.co_argcount,
                    vars,
                    FRAME_KIND_PYTHON,
                    None,
                    None
                )

            frames.append(frame_info)
        
            cur_frame = cur_frame.f_back
                        
        return frames

    def send_frame_list(self, frames, thread_name = None):
        with _SendLockCtx, _NetstringConn as conn:
            conn.send(THRF)
            conn.send(struct.pack('!Q',self.id))
            write_string(conn,thread_name)
        
            # send the frame count
            conn.send(struct.pack('!I', len(frames)))
            for firstlineno, lineno, curlineno, name, filename, argcount, variables, frameKind, sourceFile, sourceLine in frames:
                # send each frame    
                conn.send(struct.pack('!I', firstlineno))
                conn.send(struct.pack('!I', lineno))
                conn.send(struct.pack('!I', curlineno))
        
                write_string(conn,name)
                write_string(conn,filename)
                conn.send(struct.pack('!I', argcount))
                
                #conn.send(struct.pack('!I', frameKind))
                #if frameKind == FRAME_KIND_DJANGO:
                #    write_string(conn,sourceFile)
                #    conn.send(struct.pack('!I', sourceLine))
                
                conn.send(struct.pack('!I', len(variables)))
                for name, type_obj, safe_repr_obj, hex_repr_obj, type_name, obj_len in variables:
                    write_string(conn,name)
                    
                    write_object(conn,type_obj, safe_repr_obj, hex_repr_obj, type_name, obj_len)

    def enum_thread_frames_locally(self):
        global threading
        if threading is None:
            import threading
        self.send_frame_list(self.get_frame_list(), getattr(threading.currentThread(), 'name', 'Python Thread'))



threading = None

class Module(object):
    """tracks information about a loaded module"""

    CurrentLoadIndex = 0

    
    def __init__(self, filename):
        # TODO: Module.CurrentLoadIndex thread safety
        self.module_id = Module.CurrentLoadIndex
        Module.CurrentLoadIndex += 1
        self.filename = filename


class ConditionInfo(object):
    def __init__(self, condition, break_when_changed):
        self.condition = condition
        self.break_when_changed = break_when_changed
        self.last_value = BREAK_WHEN_CHANGED_DUMMY

def get_code(func):
    return getattr(func, 'func_code', None) or getattr(func, '__code__', None)


class DebuggerExitException(Exception): pass

def add_break_point(modFilename, break_when_changed, condition, lineNo, brkpt_id, bound = True):
    cur_bp = BREAKPOINTS.get(lineNo)
    if cur_bp is None:
        cur_bp = BREAKPOINTS[lineNo] = dict()
    
    cond_info = None
    if condition:
        cond_info = ConditionInfo(condition, break_when_changed)
    
    cur_bp[(modFilename, brkpt_id)] = cond_info, bound

def check_break_point(modFilename, module, brkpt_id, lineNo, filename, condition, break_when_changed):
    if module.filename.lower() == path.abspath(filename).lower():
        add_break_point(modFilename, break_when_changed, condition, lineNo, brkpt_id)
        report_breakpoint_bound(brkpt_id)
        return True
    return False


class PendingBreakPoint(object):
    def __init__(self, brkpt_id, lineNo, filename, condition, break_when_changed):
        self.brkpt_id = brkpt_id
        self.lineNo = lineNo
        self.filename = filename
        self.condition = condition
        self.break_when_changed = break_when_changed

PENDING_BREAKPOINTS = set()

def mark_all_threads_for_break():
    THREADS_LOCK.acquire()
    for thread in THREADS.values():
        thread.stepping = STEPPING_BREAK
    THREADS_LOCK.release()

class DebuggerLoop(object):    
    def __init__(self, conn):
        self.conn = conn
        self.repl_backend = None
        self.command_table = {
            cmd('stpi') : self.command_step_into,
            cmd('stpo') : self.command_step_out,
            cmd('stpv') : self.command_step_over,
            cmd('brkp') : self.command_set_breakpoint,
            cmd('brkc') : self.command_set_breakpoint_condition,
            cmd('brkr') : self.command_remove_breakpoint,
            cmd('brka') : self.command_break_all,
            cmd('resa') : self.command_resume_all,
            cmd('rest') : self.command_resume_thread,
            cmd('exec') : self.command_execute_code,
            cmd('chld') : self.command_enum_children,
            cmd('setl') : self.command_set_lineno,
            cmd('detc') : self.command_detach,
            cmd('clst') : self.command_clear_stepping,
            cmd('sexi') : self.command_set_exception_info,
            cmd('sehi') : self.command_set_exception_handler_info,
            cmd('bkdr') : self.command_remove_django_breakpoint,
            cmd('bkda') : self.command_add_django_breakpoint,
            cmd('crep') : self.command_connect_repl,
            cmd('drep') : self.command_disconnect_repl,
        }

    def loop(self):
        try:
            while True:
                inp = conn.recv(4)
                cmd = self.command_table.get(inp)
                if cmd is not None:
                    cmd()
                else:
                    if inp:
                        print ('unknown command', inp)
                    break
        except DebuggerExitException:
            pass
        except socket.error:
            pass
        except:
            traceback.print_exc()
            
    def command_step_into(self):
        tid = read_long(self.conn)
        thread = get_thread_from_id(tid)
        if thread is not None:
            thread.stepping = STEPPING_INTO
            self.command_resume_all()

    def command_step_out(self):
        tid = read_long(self.conn)
        thread = get_thread_from_id(tid)
        if thread is not None:
            thread.stepping = STEPPING_OUT
            self.command_resume_all()
    
    def command_step_over(self):
        # set step over
        tid = read_long(self.conn)
        thread = get_thread_from_id(tid)
        if thread is not None:
            if DJANGO_DEBUG:
                source_obj = get_django_frame_source(thread.cur_frame)
                if source_obj is not None:
                    thread.django_stepping = True
                    self.command_resume_all()
                    return

            thread.stepping = STEPPING_OVER
            self.command_resume_all()

    def command_set_breakpoint(self):
        brkpt_id = read_uint(self.conn)
        lineNo = read_uint(self.conn)
        filename = read_string(self.conn)
        condition = read_string(self.conn)
        break_when_changed = read_uint(self.conn)
                                
        for modFilename, module in MODULES:
            if check_break_point(modFilename, module, brkpt_id, lineNo, filename, condition, break_when_changed):
                break
        else:
            # failed to set break point
            add_break_point(filename, break_when_changed, condition, lineNo, brkpt_id, False)
            PENDING_BREAKPOINTS.add(PendingBreakPoint(brkpt_id, lineNo, filename, condition, break_when_changed))
            report_breakpoint_failed(brkpt_id)

    def command_set_breakpoint_condition(self):
        brkpt_id = read_uint(self.conn)
        condition = read_string(self.conn)
        break_when_changed = read_uint(self.conn)
        
        for line, bp_dict in BREAKPOINTS.items():
            for filename, id in bp_dict:
                if id == brkpt_id:
                    bp_dict[filename, id] = ConditionInfo(condition, break_when_changed), bp_dict[filename, id][1]
                    break

    def command_remove_breakpoint(self):
        lineNo = read_uint(self.conn)
        brkpt_id = read_uint(self.conn)
        cur_bp = BREAKPOINTS.get(lineNo)
        if cur_bp is not None:
            for file, id in cur_bp:
                if id == brkpt_id:
                    del cur_bp[file, id]
                    if not cur_bp:
                        del BREAKPOINTS[lineNo]
                    break

    def command_remove_django_breakpoint(self):
        lineNo = read_uint(self.conn)
        brkpt_id = read_uint(self.conn)
        filename = read_string(self.conn)

        bp_info = DJANGO_BREAKPOINTS.get(filename.lower())
        if bp_info is not None:
            bp_info.remove_breakpoint(lineNo)

    def command_add_django_breakpoint(self):
        brkpt_id = read_uint(self.conn)
        lineNo = read_uint(self.conn)
        filename = read_string(self.conn)
        bp_info = DJANGO_BREAKPOINTS.get(filename.lower())
        if bp_info is None:
            DJANGO_BREAKPOINTS[filename.lower()] = bp_info = DjangoBreakpointInfo(filename)

        bp_info.add_breakpoint(lineNo, brkpt_id)

    def command_connect_repl(self):
        port_num = read_uint(self.conn)
        _start_new_thread(self.connect_to_repl_backend, (port_num,))

    def connect_to_repl_backend(self, port_num):
        DONT_DEBUG.append(visualstudio_py_repl.__file__)
        self.repl_backend = visualstudio_py_repl.DebugReplBackend(self)
        self.repl_backend.connect_from_debugger(port_num)
        self.repl_backend.execution_loop()

    def command_disconnect_repl(self):
        self.repl_backend.disconnect_from_debugger()
        self.repl_backend = None

    def command_break_all(self):
        global SEND_BREAK_COMPLETE
        SEND_BREAK_COMPLETE = True
        mark_all_threads_for_break()

    def command_resume_all(self):
        # resume all
        THREADS_LOCK.acquire()
        all_threads = list(THREADS.values())
        THREADS_LOCK.release()
        for thread in all_threads:
            thread._block_starting_lock.acquire()
            if thread.stepping == STEPPING_BREAK or thread.stepping == STEPPING_ATTACH_BREAK:
                thread.stepping = STEPPING_NONE
            if thread._is_blocked:
                thread.unblock()
            thread._block_starting_lock.release()
    
    def command_resume_thread(self):
        tid = read_long(self.conn)
        THREADS_LOCK.acquire()
        thread = THREADS[tid]
        THREADS_LOCK.release()

        if thread.reported_process_loaded:
            thread.reported_process_loaded = False
            self.command_resume_all()
        else:
            thread.unblock()
    
    def command_set_exception_info(self):
        BREAK_ON.Clear()
        BREAK_ON.default_mode = read_uint(self.conn)

        break_on_count = read_uint(self.conn)
        for i in xrange(break_on_count):
            mode = read_uint(self.conn)
            name = read_string(self.conn)
            BREAK_ON.AddException(name, mode)

    def command_set_exception_handler_info(self):
        try:
            filename = read_string(self.conn)

            statement_count = read_uint(self.conn)
            handlers = []
            for _ in xrange(statement_count):
                line_start, line_end = read_int(self.conn), read_uint(self.conn)

                if line_start == -1:
                    line_start = None

                expressions = set()
                text = read_string(self.conn).strip()
                while text != '-':
                    expressions.add(text)
                    text = read_string(self.conn)

                if not expressions:
                    expressions = set('*')

                handlers.append((line_start, line_end, expressions))

            BREAK_ON.handler_cache[filename] = handlers
        finally:
            BREAK_ON.handler_lock.release()

    def command_clear_stepping(self):
        tid = read_long(self.conn)

        thread = get_thread_from_id(tid)
        if thread is not None:
            thread.stepping = STEPPING_NONE

    def command_set_lineno(self):
        tid = read_long(self.conn)
        fid = read_uint(self.conn)
        lineno = read_uint(self.conn)
        try:
            THREADS_LOCK.acquire()
            THREADS[tid].cur_frame.f_lineno = lineno
            newline = THREADS[tid].cur_frame.f_lineno
            THREADS_LOCK.release()
            with _SendLockCtx, _NetstringWrapper(self.conn) as conn:
                conn.send(SETL)
                conn.send(struct.pack('!I', 1))
                conn.send(struct.pack('!Q', tid))
                conn.send(struct.pack('!I', newline))
        except:
            with _SendLockCtx, _NetstringWrapper(self.conn) as conn:
                conn.send(SETL)
                conn.send(struct.pack('!I', 0))
                conn.send(struct.pack('!Q', tid))
                conn.send(struct.pack('!I', 0))

    def command_execute_code(self):
        # execute given text in specified frame
        text = read_string(self.conn)
        tid = read_long(self.conn) # thread id
        fid = read_uint(self.conn) # frame id
        eid = read_uint(self.conn) # execution id
        frame_kind = read_uint(self.conn)

        thread, cur_frame = self.get_thread_and_frame(tid, fid, frame_kind)
        if thread is not None and cur_frame is not None:
            thread.run_on_thread(text, cur_frame, eid, frame_kind)

    def execute_code_no_report(self, text, tid, fid, frame_kind):
        # execute given text in specified frame, without sending back the results
        thread, cur_frame = self.get_thread_and_frame(tid, fid, frame_kind)
        if thread is not None and cur_frame is not None:
            thread.run_locally_no_report(text, cur_frame, frame_kind)

    def command_enum_children(self):
        # execute given text in specified frame
        text = read_string(self.conn)
        tid = read_long(self.conn) # thread id
        fid = read_uint(self.conn) # frame id
        eid = read_uint(self.conn) # execution id
        frame_kind = read_uint(self.conn) # frame kind
        child_is_enumerate = read_uint(self.conn)
                
        thread, cur_frame = self.get_thread_and_frame(tid, fid, frame_kind)
        if thread is not None and cur_frame is not None:
            thread.enum_child_on_thread(text, cur_frame, eid, child_is_enumerate, frame_kind)
    
    def get_thread_and_frame(self, tid, fid, frame_kind):
        thread = get_thread_from_id(tid)
        cur_frame = None

        if thread is not None:
            cur_frame = thread.cur_frame
            for i in xrange(fid):
                cur_frame = cur_frame.f_back

        return thread, cur_frame

    def command_detach(self):
        detach_threads()

        # unload debugger DLL
        global debugger_dll_handle
        if debugger_dll_handle is not None:
            k32 = ctypes.WinDLL('kernel32')
            k32.FreeLibrary.argtypes = [ctypes.c_void_p]
            k32.FreeLibrary(debugger_dll_handle)
            debugger_dll_handle = None

        with _SendLockCtx, _NetstringConn as conn:
            conn.send(DETC)

            detach_process()        

        for callback in DETACH_CALLBACKS:
            callback()
        
        raise DebuggerExitException()


DETACH_CALLBACKS = []

def new_thread_wrapper(func, *posargs, **kwargs):
    cur_thread = new_thread()
    try:
        sys.settrace(cur_thread.trace_func)
        func(*posargs, **kwargs)
    finally:
        THREADS_LOCK.acquire()
        if not cur_thread.detach:
            del THREADS[cur_thread.id]
        THREADS_LOCK.release()

        if not DETACHED:
            report_thread_exit(cur_thread)

def write_string(conn,string):
    if string is None:
        conn.send(NONE_PREFIX)
    elif isinstance(string, unicode):
        bytes = string.encode('utf8')
        conn.send(UNICODE_PREFIX)
        conn.send(struct.pack('!I', len(bytes)))
        conn.send(bytes)
    else:
        conn.send(ASCII_PREFIX)
        conn.send(struct.pack('!I', len(string)))
        conn.send(string)

def read_string(conn):
    str_len = read_uint(conn)
    if not str_len:
        return ''
    res = cmd('')
    while len(res) < str_len:
        res = res + conn.recv(str_len - len(res))
    return res.decode('utf8')

def read_int(conn):
    return struct.unpack('!i', conn.recv(4))[0]

def read_uint(conn):
    return struct.unpack('!I', conn.recv(4))[0]

def read_long(conn):
    return struct.unpack('!Q', conn.recv(8))[0]

def report_new_thread(new_thread):
    ident = new_thread.id
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(NEWT)
        conn.send(struct.pack('!Q', ident))

def report_thread_exit(old_thread):
    ident = old_thread.id
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(EXTT)
        conn.send(struct.pack('!Q', ident))

def report_exception(frame, exc_info, tid, break_type):
    exc_type = exc_info[0]
    exc_value = exc_info[1]
    tb_value = exc_info[2]
    exc_name = exc_type.__module__ + '.' + exc_type.__name__
    
    if type(exc_value) is tuple:
        # exception object hasn't been created yet, create it now 
        # so we can get the correct msg.
        exc_value = exc_type(*exc_value)
    
    excp_text = str(exc_value)

    with _SendLockCtx, _NetstringConn as conn:
        conn.send(EXCP)
        write_string(conn,exc_name)
        conn.send(struct.pack('!Q', tid))
        conn.send(struct.pack('!I', break_type))
        write_string(conn,excp_text)

def new_module(frame):
    mod = Module(get_code_filename(frame.f_code))
    MODULES.append((frame.f_code.co_filename, mod))

    return frame.f_code, mod

def report_module_load(mod):
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(MODL)
        conn.send(struct.pack('!Q', mod.module_id))
        write_string(conn,mod.filename)

def report_step_finished(tid):
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(STPD)
        conn.send(struct.pack('!Q', tid))

def report_breakpoint_bound(id):
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(BRKS)
        conn.send(struct.pack('!I', id))

def report_breakpoint_failed(id):
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(BRKF)
        conn.send(struct.pack('!I', id))

def report_breakpoint_hit(id, tid):
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(BRKH)
        conn.send(struct.pack('!I', id))
        conn.send(struct.pack('!Q', tid))

def report_process_loaded(tid):
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(LOAD)
        conn.send(struct.pack('!Q', tid))

def report_execution_error(exc_text, execution_id):
    with _SendLockCtx, _NetstringConn as conn:
        conn.send(EXCE)
        conn.send(struct.pack('!I', execution_id))
        write_string(conn,exc_text)

def report_execution_exception(execution_id, exc_info):
    try:
        exc_text = str(exc_info[1])
    except:
        exc_text = 'An exception was thrown'

    report_execution_error(exc_text, execution_id)

def safe_repr(obj):
    try:
        return repr(obj)
    except:
        return '__repr__ raised an exception'

def safe_hex_repr(obj):
    try:
        return hex(obj)
    except:
        return None

def get_object_len(obj):
    try:
        return len(obj)
    except:
        return None

def report_execution_result(execution_id, result):
    obj_repr = safe_repr(result)
    hex_repr = safe_hex_repr(result)
    res_type = type(result)
    type_name = type(result).__name__
    obj_len = get_object_len(result)

    with _SendLockCtx, _NetstringConn as conn:
        conn.send(EXCR)
        conn.send(struct.pack('!I', execution_id))
        write_object(conn,res_type, obj_repr, hex_repr, type_name, obj_len)

def report_children(execution_id, attributes, indices, indices_are_index, indices_are_enumerate):
    attributes = [(index, safe_repr(result), safe_hex_repr(result), type(result), type(result).__name__, get_object_len(result)) for index, result in attributes]
    indices = [(index, safe_repr(result), safe_hex_repr(result), type(result), type(result).__name__, get_object_len(result)) for index, result in indices]

    with _SendLockCtx, _NetstringConn as conn:
        conn.send(CHLD)
        conn.send(struct.pack('!I', execution_id))
        conn.send(struct.pack('!I', len(attributes)))
        conn.send(struct.pack('!I', len(indices)))
        conn.send(struct.pack('!I', indices_are_index))
        conn.send(struct.pack('!I', indices_are_enumerate))
        for child_name, obj_repr, hex_repr, res_type, type_name, obj_len in attributes:
            write_string(conn,child_name)
            write_object(conn,res_type, obj_repr, hex_repr, type_name, obj_len)
        for child_name, obj_repr, hex_repr, res_type, type_name, obj_len in indices:
            write_string(conn,child_name)
            write_object(conn,res_type, obj_repr, hex_repr, type_name, obj_len)

def get_code_filename(code):
    return path.abspath(code.co_filename)

NONEXPANDABLE_TYPES = set([int, str, bool, float, object, type(None), unicode])
try:
    NONEXPANDABLE_TYPES.add(long)
except NameError: pass

def write_object(conn,obj_type, obj_repr, hex_repr, type_name, obj_len):
    write_string(conn,obj_repr)
    write_string(conn,hex_repr)
    write_string(conn,type_name)
    if obj_type in NONEXPANDABLE_TYPES or obj_len == 0:
        conn.send(struct.pack('!I', 0))
    else:
        conn.send(struct.pack('!I', 1))


try:
    execfile
except NameError:
    # Py3k, execfile no longer exists
    def execfile(file, globals, locals): 
        f = open(file, "rb")
        try:
            exec(compile(f.read().replace(cmd('\r\n'), cmd('\n')), file, 'exec'), globals, locals) 
        finally:
            f.close()


debugger_thread_id = -1
_INTERCEPTING_FOR_ATTACH = False
def intercept_threads(for_attach = False):
    thread.start_new_thread = thread_creator
    thread.start_new = thread_creator
    global threading
    if threading is None:
        # we need to patch threading._start_new_thread so that 
        # we pick up new threads in the attach case when threading
        # is already imported.
        import threading
        threading._start_new_thread = thread_creator
    global _INTERCEPTING_FOR_ATTACH
    _INTERCEPTING_FOR_ATTACH = for_attach


def attach_process(port_num, debug_id, report_and_block = False):
    global conn
    for i in xrange(50):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect(('127.0.0.1', port_num))
            with _NetstringConn as con:
                con.send(CONN)
                write_string(con,debug_id)
                con.send(struct.pack('!I', 0))  # success
            break
        except:
            import time
            time.sleep(50./1000)
    else:
        raise Exception('failed to attach')

    global DETACHED
    global attach_sent_break
    DETACHED = False
    attach_sent_break = False

    # start the debugging loop
    global debugger_thread_id
    debugger_thread_id = _start_new_thread(DebuggerLoop(conn).loop, ())

    if report_and_block:
        THREADS_LOCK.acquire()
        main_thread = THREADS[thread.get_ident()]
        for cur_thread in THREADS.values():
            report_new_thread(cur_thread)

        THREADS_LOCK.release()

        for filename, module in MODULES:
            report_module_load(module)            

        main_thread.block(lambda: report_process_loaded(thread.get_ident()))

    for mod_name, mod_value in sys.modules.items():
        try:
            filename = getattr(mod_value, '__file__', None)
            if filename is not None:
                try:
                    fullpath = path.abspath(filename)
                except:
                    pass
                else:
                    MODULES.append((filename, Module(fullpath)))
        except:
            traceback.print_exc()   

    # intercept all new thread requests
    if not _INTERCEPTING_FOR_ATTACH:
        intercept_threads()

def detach_process():
    global DETACHED
    DETACHED = True
    if not _INTERCEPTING_FOR_ATTACH:
        if isinstance(sys.stdout, _DebuggerOutput): 
            sys.stdout = sys.stdout.old_out
        if isinstance(sys.stderr, _DebuggerOutput):
            sys.stderr = sys.stderr.old_out

    if not _INTERCEPTING_FOR_ATTACH:
        thread.start_new_thread = _start_new_thread
        thread.start_new = _start_new_thread

def detach_threads():
    # tell all threads to stop tracing...
    THREADS_LOCK.acquire()
    for tid, pyThread in THREADS.items():
        if not _INTERCEPTING_FOR_ATTACH:
            pyThread.detach = True
            pyThread.stepping = STEPPING_BREAK

        if pyThread._is_blocked:
            pyThread.unblock()

    if not _INTERCEPTING_FOR_ATTACH:
        THREADS.clear()

    BREAKPOINTS.clear()

    THREADS_LOCK.release()

def new_thread(tid = None, set_break = False, frame = None):
    # called during attach w/ a thread ID provided.
    if tid == debugger_thread_id:
        return None

    cur_thread = Thread(tid)    
    THREADS_LOCK.acquire()
    THREADS[cur_thread.id] = cur_thread
    THREADS_LOCK.release()
    cur_thread.push_frame(frame)
    if set_break:
        cur_thread.stepping = STEPPING_ATTACH_BREAK
    if not DETACHED:
        report_new_thread(cur_thread)
    return cur_thread

def new_external_thread():
    thread = new_thread()
    if not attach_sent_break:
        # we are still doing the attach, make this thread break.
        thread.stepping = STEPPING_ATTACH_BREAK
    elif SEND_BREAK_COMPLETE:
        # user requested break all, make this thread break
        thread.stepping = STEPPING_BREAK

    sys.settrace(thread.trace_func)

def do_wait():
    sys.__stdout__.write('Press any key to continue . . . ')
    sys.__stdout__.flush()
    getch()

class _DebuggerOutput(object):
    """file like object which redirects output to the repl window."""
    errors = 'strict'

    def __init__(self, old_out, is_stdout):
        self.is_stdout = is_stdout
        self.old_out = old_out
        if sys.version >= '3.' and hasattr(old_out, 'buffer'):
            self.buffer = DebuggerBuffer(old_out.buffer)

    def flush(self):
        if self.old_out:
            self.old_out.flush()
    
    def writelines(self, lines):
        for line in lines:
            self.write(line)
    
    @property
    def encoding(self):
        return 'utf8'

    def write(self, value):
        if not DETACHED:
            probe_stack(3)
            with _SendLockCtx, _NetstringConn as conn:
                conn.send(OUTP)
                conn.send(struct.pack('!Q', thread.get_ident()))
                write_string(conn,value)
        if self.old_out:
            self.old_out.write(value)
    
    def isatty(self):
        return True

    def next(self):
        pass
    
    @property
    def name(self):
        if self.is_stdout:
            return "<stdout>"
        else:
            return "<stderr>"

class DebuggerBuffer(object):
    def __init__(self, old_buffer):
        self.buffer = old_buffer

    def write(self, data):
        if not DETACHED:
            probe_stack(3)
            str_data = data.decode('utf8')
            with _SendLockCtx, _NetstringConn as conn:
                conn.send(OUTP)
                conn.send(struct.pack('!Q', thread.get_ident()))
                write_string(conn,str_data)
        self.buffer.write(data)

    def flush(self): 
        self.buffer.flush()

    def truncate(self, pos = None):
        return self.buffer.truncate(pos)

    def tell(self):
        return self.buffer.tell()

    def seek(self, pos, whence = 0):
        return self.buffer.seek(pos, whence)


def is_same_py_file(file1, file2):
    """compares 2 filenames accounting for .pyc files"""
    if file1.endswith('.pyc') or file1.endswith('.pyo'): 
        file1 = file1[:-1]
    if file2.endswith('.pyc') or file2.endswith('.pyo'): 
        file2 = file2[:-1]

    return file1 == file2


def print_exception():
    # count the debugger frames to be removed
    tb = traceback.extract_tb(sys.exc_info()[2])
    debugger_count = len(tb)
    while debugger_count:
        if is_same_py_file(tb[debugger_count - 1][0], __file__):
            break
        debugger_count -= 1
        
    # print the traceback
    tb = tb[debugger_count:]
    if tb:
        print('Traceback (most recent call last):')
        for out in traceback.format_list(tb):
            sys.stdout.write(out)
    
    # print the exception
    for out in traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1]):
        sys.stdout.write(out)

def silent_excepthook(exc_type, exc_value, exc_tb):
    # Used to avoid displaying the exception twice on exit.
    pass

def debug(file, port_num, debug_id, globals_obj, locals_obj, wait_on_exception, redirect_output, wait_on_exit, break_on_systemexit_zero = False, debug_stdlib = False, django_debugging = False):
    # remove us from modules so there's no trace of us
    sys.modules['$visualstudio_py_debugger'] = sys.modules['visualstudio_py_debugger']
    __name__ = '$visualstudio_py_debugger'
    del sys.modules['visualstudio_py_debugger']
    del globals_obj['port_num']
    del globals_obj['visualstudio_py_debugger']
    del globals_obj['wait_on_exception']
    del globals_obj['redirect_output']
    del globals_obj['wait_on_exit']
    del globals_obj['debug_id']
    del globals_obj['django_debugging']
    if 'break_on_systemexit_zero' in globals_obj: 
        del globals_obj['break_on_systemexit_zero']
    if 'debug_stdlib' in globals_obj: 
        del globals_obj['debug_stdlib']

    global BREAK_ON_SYSTEMEXIT_ZERO, DEBUG_STDLIB, DJANGO_DEBUG
    BREAK_ON_SYSTEMEXIT_ZERO = break_on_systemexit_zero
    DEBUG_STDLIB = debug_stdlib
    DJANGO_DEBUG = django_debugging

    attach_process(port_num, debug_id)

    if redirect_output:
        sys.stdout = _DebuggerOutput(sys.stdout, is_stdout = True)
        sys.stderr = _DebuggerOutput(sys.stderr, is_stdout = False)

    # setup the current thread
    cur_thread = new_thread()
    cur_thread.stepping = STEPPING_LAUNCH_BREAK

    # start tracing on this thread
    sys.settrace(cur_thread.trace_func)

    # now execute main file
    try:
        try:
            execfile(file, globals_obj, locals_obj)
        finally:
            sys.settrace(None)
            THREADS_LOCK.acquire()
            if THREADS:
                del THREADS[cur_thread.id]
            THREADS_LOCK.release()
            report_thread_exit(cur_thread)

        if wait_on_exit:
            do_wait()
    except SystemExit:
        if (wait_on_exception and sys.exc_info()[1].code != 0) or (wait_on_exit and sys.exc_info()[1].code == 0):
            print_exception()
            do_wait()
        if sys.excepthook == sys.__excepthook__:
            # If the user has reassigned excepthook then let theirs run.
            # Otherwise, suppress the extra traceback.
            sys.excepthook = silent_excepthook
        raise
    except:
        print_exception()
        if wait_on_exception:
            do_wait()
        if sys.excepthook == sys.__excepthook__:
            # If the user has reassigned excepthook then let theirs run.
            # Otherwise, suppress the extra traceback.
            sys.excepthook = silent_excepthook
        raise
