import os

# Enthought library imports.
from pyface.tasks.api import TraitsDockPane
from traits.api import Event, List, Instance
from traitsui.api import View, Item, ListStrEditor
from traitsui.list_str_adapter import ListStrAdapter

from python_process import PythonStackFrame


class StackAdapter(ListStrAdapter):
    """ Adapt from PythonStackFrame
    """

    def _get_text(self):
        f = self.item
        filename = os.path.basename(f._filename)
        line = ''
        return ('%s, Line %d, in %s(%d-%d)\n%s'
                 %(filename, f._lineNo, f._frameName, f._startLine, f._endLine, line))

class StackPane(TraitsDockPane):
    """ A simple listing of stack panes
    """

    #### TaskPane interface ###################################################

    id = 'debugger.stack_pane'
    name = 'Stack Frames'

    #### FileBrowserPane interface ############################################

    # The list of stack frames
    stack_frames = List(Instance(PythonStackFrame))

    # The currently selected frame.
    selected = Instance(PythonStackFrame)

    frame_adapter = Instance(StackAdapter, ())

    # The view used to construct the dock pane's widget.
    view = View(Item('stack_frames',
                     editor=ListStrEditor(selected='selected',
                                          horizontal_lines=True,
                                          operations=[],
                                          adapter_name='frame_adapter',
                                          ),
                     style='custom',
                     show_label=False),
                resizable=True)

    def _stack_frames_changed(self, frames):
        self.selected = frames[0]
