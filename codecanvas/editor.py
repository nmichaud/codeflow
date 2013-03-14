import sys, re
from string import ascii_letters
from PySide.QtCore import *
from PySide.QtGui import *
from CanopyTextEdit import TextEdit, TextCursor, TextDocument, SyntaxHighlighter

class SpellCheck(SyntaxHighlighter):
    def highlightBlock(self, text):
        if re.search("[0-9]", text):
            format = QTextCharFormat()
            format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            self.setFormat(0, len(text), format)

class SpecialHighlighter(SyntaxHighlighter):
    def highlightBlock(self, text):
        state = 'space'
        last = 0
        for i in range(len(text)):
            if text[i] == ' ':
                if state != 'space':
                    self.helper(last, i - last, state == 'alphanum')
                state = 'space'
                last = i
            elif ((text[i] in ascii_letters) != (state == 'alphanum')) or state == 'space':
                if state != 'space':
                    self.helper(last, i-last, state == 'alphanum')
                state = 'alphanum' if text[i] in ascii_letters else 'other'
                last = i
        if state != 'space':
            self.helper(last, len(text)-last, state == 'alphanum')

    def helper(self, start, size, blackForeground):
        format = QTextCharFormat()
        format.setBackground(Qt.yellow if blackForeground else Qt.black)
        format.setForeground(Qt.black if blackForeground else Qt.yellow)
        self.setFormat(start, size, format)

class BlockLight(SyntaxHighlighter):
    def highlightBlock(self, text):
        format = QTextCharFormat()
        format.setBackground(Qt.yellow)
        self.setFormat(0, min(4, len(text)), format)
        f = QFont()
        f.setPixelSize(30)
        self.setFormat(0, min(4, len(text)), f)

class Editor(TextEdit):
    cursorCharacter = Signal(unicode)

    def __init__(self, parent=None):
        super(Editor, self).__init__(parent)
        self.setAttribute(Qt.WA_MouseTracking)

    def mouseMoveEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        if cursor.isValid():
            self.cursorCharacter.emit(cursor.cursorCharacter())
        super(Editor, self).mouseMoveEvent(event)
