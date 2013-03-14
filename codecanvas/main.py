import sys
from PySide.QtCore import *
from PySide.QtGui import *

from editor import Editor
from highlighters import PythonHighlighter as Highlighter
from styles import IPythonStyle as Style
from codecanvas import InfiniteCanvas

class EditingWidget(QGraphicsWidget):
    def __init__(self, scene, parent=None):
        super(EditingWidget, self).__init__(parent, Qt.Tool)

        fileName = 'main.py'

        layout = QGraphicsLinearLayout()
        self.setLayout(layout)

        self.textEdit = textEdit = Editor() #self)
        textEdit.setCursorWidth(2)
        textEdit.setObjectName('primary')

        #textEdit.cursorCharacter.connect(self.onCursorCharacterChanged)
        #textEdit.cursorPositionChanged.connect(self.onCursorPositionChanged)
        textEdit.sectionClicked.connect(self.onTextSectionClicked)
        #textEdit.document().modificationChanged.connect(self.onModificationChanged)

        layout.addItem(scene.addWidget(self.textEdit))
        #layout.addWidget(self.textEdit)

        textEdit.load(fileName)

        self.highlighter = Highlighter(textEdit, Style())

        #shortcut = QShortcut(QKeySequence(Qt.CTRL + Qt.Key_E), textEdit)
        #shortcut.activated.connect(textEdit.ensureCursorVisible)
        #self._shortcuts = [shortcut]

        #shortcut = QShortcut(QKeySequence(Qt.CTRL + Qt.Key_M), self)
        #shortcut.activated.connect(self.markLine)
        #self._shortcuts.append(shortcut)

        textEdit.viewport().setAutoFillBackground(True)

    def onModificationChanged(self, on):
        pal = self.textEdit.viewport().palette()
        pal.setColor(self.textEdit.viewport().backgroundRole(), Qt.yellow if on else Qt.white)
        self.textEdit.viewport().setPalette(pal)

    def markLine(self):
        cursor = self.textEdit.textCursor()
        cursor.movePosition(TextCursor.StartOfLine);
        cursor.movePosition(TextCursor.Down, TextCursor.KeepAnchor);
        cursor.movePosition(TextCursor.EndOfLine, TextCursor.KeepAnchor);
        format = QTextCharFormat()
        format.setBackground(Qt.red);
        selection = TextEdit.ExtraSelection(cursor, format)
        textEdit.setExtraSelections([selection])

    def onTextSectionClicked(self, section, pos):
        print section.text(), section.data(), pos


if __name__ == '__main__':
    app = QApplication.instance()

    scene = QGraphicsScene()

    proxy = EditingWidget(scene)
    effect = QGraphicsDropShadowEffect()
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(3)
    effect = QGraphicsOpacityEffect()
    effect.setOpacity(0.2)
    #proxy.setGraphicsEffect(effect)
    scene.addItem(proxy)
    #proxy = scene.addItem(EditingWidget(scene))
    proxy.resize(500,500)

    view = InfiniteCanvas(scene)
    view.setWindowTitle("Code Canvas")
    view.resize(800, 600)
    view.show()
    sys.exit(app.exec_())
