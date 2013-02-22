#------------------------------------------------------------------------------
# Copyright (c) 2010, Enthought Inc
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD license.

#
# Author: Enthought Inc
# Description: <Enthought pyface code editor>
#------------------------------------------------------------------------------

from pyface.qt import QtCore, QtGui


class CodeOverlay(QtGui.QWidget):

    def __init__(self, parent):
        assert isinstance(parent, QtGui.QPlainTextEdit)
        super(CodeOverlay, self).__init__(parent)

        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self._font = font = QtGui.QFont('Courier', 12)
        font.setStyleHint(QtGui.QFont.Serif)

        self._timings = {}

    def setTimings(self, timings):
        self._timings = timings
        self.update()

    def paintEvent(self, event):
        """ Paint the timings
        """

        painter = QtGui.QPainter(self)

        cw = self.parent()

        document = cw.document()
        text_font = document.defaultFont()
        textFontMetrics = QtGui.QFontMetrics(text_font)

        msg_font = self._font
        msgFontMetrics = QtGui.QFontMetrics(msg_font)
        leading = msgFontMetrics.leading()
        painter.setFont(msg_font)

        offset = cw.contentOffset()

        block = cw.firstVisibleBlock()
        geometry = cw.blockBoundingGeometry(block).translated(offset)
        top = geometry.top()
        bottom = top + geometry.height()

        right_margin = 20

        template = '%9s %12s %8s %8s'

        if self._timings:
            # Print a header at the top
            rect = QtCore.QRectF(geometry).adjusted(0,0,-right_margin, 0)
            painter.drawText(rect,
                QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter,
                template % ('Hits', 'Time', 'Per Hit', '% Time'))

            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible() and bottom >= event.rect().top():
                    blockNum = block.blockNumber() + 1

                    rect = QtCore.QRectF(geometry).adjusted(0,0,-right_margin, 0)
                    timings = self._timings.get(blockNum)
                    if timings:
                        nhits, time, per_hit, percent = timings
                        painter.drawText(rect,
                            QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter,
                            template % (nhits, time, '%5.1f'%per_hit, '%5.1f'%percent))

                block = block.next()
                geometry = cw.blockBoundingGeometry(block).translated(offset)
                top = geometry.top()
                bottom = top + geometry.height()

