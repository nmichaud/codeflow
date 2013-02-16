# Enthought library imports.
from pyface.tasks.api import Task, TaskLayout, PaneItem, IEditor, \
    IEditorAreaPane, SplitEditorAreaPane
from pyface.tasks.action.api import DockPaneToggleGroup, SMenuBar, \
    SMenu, SToolBar, TaskAction
from pyface.api import ConfirmationDialog, FileDialog, \
    ImageResource, YES, OK, CANCEL

from traits.api import on_trait_change, Property, Instance, Bool

# Local imports.
from file_panes import PythonScriptBrowserPane
from python_editor import PythonEditor

class DebuggerTask(Task):
    """ A simple task for editing Python code.
    """

    #### Task interface #######################################################

    id = 'debugger.debugger_task'
    name = 'Debugging Editor'

    active_editor = Property(Instance(IEditor),
                             depends_on='editor_area.active_editor')

    editor_area = Instance(IEditorAreaPane)

    menu_bar = SMenuBar(SMenu(TaskAction(name='New', method='new',
                                         accelerator='Ctrl+N'),
                              TaskAction(name='Open...', method='open',
                                         accelerator='Ctrl+O'),
                              TaskAction(name='Save', method='save',
                                         accelerator='Ctrl+S'),
                              id='File', name='&File'),
                        SMenu(DockPaneToggleGroup(),
                              id='View', name='&View'))

    tool_bars = [ SToolBar(TaskAction(method='new',
                                      tooltip='New file',
                                      image=ImageResource('document_new')),
                           TaskAction(method='open',
                                      tooltip='Open a file',
                                      image=ImageResource('document_open')),
                           TaskAction(method='save',
                                      tooltip='Save the current file',
                                      image=ImageResource('document_save')),
                           image_size = (24, 24)),
                  SToolBar(TaskAction(method='start_debugger',
                                      tooltip='Start debugger',
                                      enabled_name = 'ready_to_debug',
                                      image=ImageResource('debugger_start')),
                           TaskAction(method='stop_debugger',
                                      tooltip='Stop debugger',
                                      enabled_name = 'debugger_service.running',
                                      image=ImageResource('debugger_stop')),
                           TaskAction(method='step_over_line',
                                      tooltip='Step over next line',
                                      enabled_name = 'debugger_running',
                                      image=ImageResource('debugger_step_over')),
                           TaskAction(method='step_into_line',
                                      tooltip='Step into next line',
                                      enabled_name = 'debugger_running',
                                      image=ImageResource('debugger_step_into')),
                           TaskAction(method='step_out',
                                      tooltip='Step out of the current function',
                                      enabled_name = 'debugger_running',
                                      image=ImageResource('debugger_step_out')),
                           image_size = (24, 24)),
                ]

    ###########################################################################
    # 'Task' interface.
    ###########################################################################

    def _default_layout_default(self):
        return TaskLayout(
            left=PaneItem('debugger.python_script_browser_pane'))

    def activated(self):
        """ Overriden to set the window's title.
        """
        return
        filename = self.active_editor.path if self.active_editor else ''
        self.window.title = filename if filename else 'Untitled'

    def create_central_pane(self):
        """ Create the central pane: the script editor.
        """
        self.editor_area = SplitEditorAreaPane()
        return self.editor_area

    def create_dock_panes(self):
        """ Create the file browser and connect to its double click event.
        """
        browser = PythonScriptBrowserPane()
        handler = lambda: self._open_file(browser.selected_file)
        browser.on_trait_change(handler, 'activated')
        return [ browser ]

    ###########################################################################
    # 'DebuggerTask' interface.
    ###########################################################################

    debugger_service = Instance('plugins.debugger.debugger_service.DebuggerService')

    debugger_running = Bool(False)
    ready_to_debug = Property(Bool, depends_on='active_editor')

    def _get_ready_to_debug(self):
        return self.active_editor != None

    def new(self):
        """ Opens a new empty window
        """
        editor = PythonEditor()
        self.editor_area.add_editor(editor)
        self.editor_area.activate_editor(editor)
        self.activated()

    def open(self):
        """ Shows a dialog to open a file.
        """
        dialog = FileDialog(parent=self.window.control, wildcard='*.py')
        if dialog.open() == OK:
            self._open_file(dialog.path)

    def save(self):
        """ Attempts to save the current file, prompting for a path if
            necessary. Returns whether the file was saved.
        """
        editor = self.active_editor
        try:
            editor.save()
        except IOError:
            # If you are trying to save to a file that doesn't exist, open up a
            # FileDialog with a 'save as' action.
            dialog = FileDialog(parent=self.window.control,
                                action='save as', wildcard='*.py')
            if dialog.open() == OK:
                editor.save(dialog.path)
            else:
                return False
        return True

    def start_debugger(self):
        """ Start debugging the current file
        """
        editor = self.active_editor
        process = self.debugger_service.debug(editor.path)

        # Start the process
        process.Start()

    def stop_debugger(self):
        """ Stop the currently running debug instance
        """
        self.debugger_service.stop()

    def step_into_line(self):
        """ Step into the next line
        """
        pass

    def step_over_line(self):
        """ Step over the next line
        """
        pass

    def step_out(self):
        """ Step out of the current line
        """
        pass

    ###########################################################################
    # Protected interface.
    ###########################################################################

    def _open_file(self, filename):
        """ Opens the file at the specified path in the editor.
        """
        editor = PythonEditor(path=filename)
        self.editor_area.add_editor(editor)
        self.editor_area.activate_editor(editor)
        self.activated()

    def _prompt_for_save(self):
        """ Prompts the user to save if necessary. Returns whether the dialog
            was cancelled.
        """
        dirty_editors = dict([(editor.name, editor)
                              for editor in self.editor_area.editors
                              if editor.dirty])
        if not dirty_editors.keys():
            return True
        message = 'You have unsaved files. Would you like to save them?'
        dialog = ConfirmationDialog(parent=self.window.control,
                                    message=message, cancel=True,
                                    default=CANCEL, title='Save Changes?')
        result = dialog.open()
        if result == CANCEL:
            return False
        elif result == YES:
            for name, editor in dirty_editors.items():
                editor.save(editor.path)
        return True

    #### Trait change handlers ################################################

    @on_trait_change('window:closing')
    def _prompt_on_close(self, event):
        """ Prompt the user to save when exiting.
        """
        close = self._prompt_for_save()
        event.veto = not close

    #### Trait property getter/setters ########################################

    def _get_active_editor(self):
        if self.editor_area is not None:
            return self.editor_area.active_editor
        return None
