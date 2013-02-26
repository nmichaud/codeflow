#------------------------------------------------------------------------------
# Copyright (c) 2010, Enthought Inc
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD license.

#
# Author: Enthought Inc
# Description: <Enthought pyface code editor>
#------------------------------------------------------------------------------

import math
from pyface.qt import QtCore, QtGui


class CodeOverlay(QtGui.QWidget):

    def __init__(self, parent):
        assert isinstance(parent, QtGui.QPlainTextEdit)
        super(CodeOverlay, self).__init__(parent)

        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self._font = font = QtGui.QFont('Courier', 12)
        font.setStyleHint(QtGui.QFont.Serif)

        self._timings = {}
        self._animate = 0
        self._a = None

    def setTimings(self, timings):
        if timings:
            self._timings = timings
            self.showTimings()
        else:
            self.hideTimings(timings)

    def showTimings(self):
        if self._a: self._a.stop()

        self._a = anim = QtCore.QPropertyAnimation(self, 'animate', self)
        anim.setDuration(400)
        anim.setStartValue(0.01)
        anim.setEndValue(1)

        anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        anim.start()

    def hideTimings(self, timings):
        if self._a: self._a.stop()

        self._a = anim = QtCore.QPropertyAnimation(self, 'animate', self)
        anim.setDuration(400)
        anim.setStartValue(1)
        anim.setEndValue(0.0)

        anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        anim.start()
        anim.finished.connect(lambda: setattr(self, '_timings', timings))

    def set_animate(self, val):
        self._animate = val
        self.repaint()

    animate = QtCore.Property(float, fget=lambda self: self._animate, fset=set_animate)

    def calc_color(self, percent):
        start = 254, 224, 210
        end = 222, 45, 38
        alpha = 150./255
        premul = 255*(1-alpha)
        red = ((1-percent)*start[0] + percent*end[0])*alpha + premul
        green = ((1-percent)*start[1] + percent*end[1])*alpha + premul
        blue = ((1-percent)*start[2] + percent*end[2])*alpha + premul
        return QtGui.QColor(red, green, blue)

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

        template = '%7s %12s %8s %8s'

        timing_bg = QtGui.QColor(227, 229, 235)
        painter.setPen(timing_bg)
        painter.setBrush(timing_bg)

        animate = self._animate

        if self._timings:
            # Print a header at the top
            header = template % ('Hits', 'Time', 'Per Hit', '% Time')
            adjust = 10
            orig_width = width = msgFontMetrics.width(header) + adjust*2
            if animate:
                width *= animate
            rect = QtCore.QRectF(geometry).adjusted(0, 2,-right_margin, -1)
            if animate:
                left = (rect.right()-orig_width)*(animate) + (adjust)*(1-animate)
            else:
                left = rect.right() - width
            rect.setWidth(width)
            rect.moveLeft(left)
            painter.drawRoundedRect(rect,8,8)
            rect.adjust(adjust, 0, -adjust, 0)
            painter.setPen(QtCore.Qt.black)
            painter.drawText(rect,
                QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter,
                template % ('Hits', 'Time', 'Per Hit', '% Time'))

            line_pen = QtGui.QPen(timing_bg, 2, QtCore.Qt.DotLine)

            # Skip the first block

            block = block.next()
            geometry = cw.blockBoundingGeometry(block).translated(offset)
            top = geometry.top()
            bottom = top + geometry.height()

            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible() and bottom >= event.rect().top():
                    blockNum = block.blockNumber() + 1

                    rect = QtCore.QRectF(geometry).adjusted(0,0,-right_margin, 0)
                    timings = self._timings.get(blockNum)
                    if timings:

                        txt_width = textFontMetrics.width(block.text())

                        rect = QtCore.QRectF(geometry).adjusted(0,2,-right_margin, -1)
                        if animate:
                            left = (rect.right()-orig_width)*(animate) + (txt_width+adjust)*(1-animate)
                        else:
                            left = rect.right() - width
                        rect.setWidth(width)
                        rect.moveLeft(left)
                        nhits, time, per_hit, percent = timings

                        # Draw a line back to the text
                        painter.setPen(line_pen)
                        y = rect.center().y()
                        painter.drawLine(txt_width + adjust, y, rect.left(), y)
                        # Draw rect
                        color = self.calc_color(percent*0.01)
                        painter.setPen(color)
                        painter.setBrush(color)
                        painter.drawRoundedRect(rect,8,8)

                        rect.adjust(adjust, 0, -adjust, 0)
                        painter.setPen(QtCore.Qt.black)
                        painter.drawText(rect,
                            QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter,
                            template % (nhits, time, '%5.1f'%per_hit, '%5.1f'%percent))

                block = block.next()
                geometry = cw.blockBoundingGeometry(block).translated(offset)
                top = geometry.top()
                bottom = top + geometry.height()

