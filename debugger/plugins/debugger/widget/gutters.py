#------------------------------------------------------------------------------
# Copyright (c) 2010, Enthought Inc
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD license.

#
# Author: Enthought Inc
# Description: <Enthought pyface code editor>
#------------------------------------------------------------------------------

import math, re

from pyface.qt import QtCore, QtGui


class GutterWidget(QtGui.QWidget):

    min_width = 5
    background_color = QtGui.QColor("#EFEFEF")
    foreground_color = QtGui.QColor("#666666")

    def sizeHint(self):
        return QtCore.QSize(self.min_width, 0)

    def paintEvent(self, event):
        """ Paint the line numbers.
        """
        painter = QtGui.QPainter(self)
        painter.fillRect(event.rect(), QtCore.Qt.lightGray)

    def wheelEvent(self, event):
        """ Delegate mouse wheel events to parent for seamless scrolling.
        """
        self.parent().wheelEvent(event)

class StatusGutterWidget(GutterWidget):
    """ Draws status markers.
    """

    def __init__(self, *args, **kw):
        super(StatusGutterWidget, self).__init__(*args, **kw)

        self.error_lines = []
        self.warn_lines = []
        self.info_lines = []

    def sizeHint(self):
        return QtCore.QSize(10, 0)

    def paintEvent(self, event):
        """ Paint the line numbers.
        """
        painter = QtGui.QPainter(self)
        painter.fillRect(event.rect(), self.background_color)

        cw = self.parent()
        pixels_per_block = self.height()/float(cw.blockCount())

        for line in self.info_lines:
            painter.fillRect(
                QtCore.QRect(0, line*pixels_per_block, self.width(), 3),
                QtCore.Qt.green)

        for line in self.warn_lines:
            painter.fillRect(
                QtCore.QRect(0, line*pixels_per_block, self.width(), 3),
                QtCore.Qt.yellow)

        for line in self.error_lines:
            painter.fillRect(
                QtCore.QRect(0, line*pixels_per_block, self.width(), 3),
                QtCore.Qt.red)

class LineNumberWidget(GutterWidget):
    """ Draw line numbers.
    """

    min_char_width = 4

    def __init__(self, *args, **kw):
        super(LineNumberWidget, self).__init__(*args, **kw)

        self._pat = re.compile('(\s)*def |(\s)*class |(\s)*#begin-fold:')
        self._patIdent = re.compile('^\s+')
        self._foldedBlocks = set()
        self._arrow_size = 15
        self._fold_area = 0 #self._arrow_size
        self._bulge = 6
        self._generate_pixmaps(self._arrow_size)

        self._drawSymbols = False
        self._opacity = 0.
        self._anim = anim = QtCore.QPropertyAnimation(self, 'opacity', self)
        anim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        anim.setDuration(150)
        anim.setStartValue(self._opacity)
        anim.setEndValue(1.)

    def _generate_pixmaps(self, size):
        self._rightArrow = right = QtGui.QPixmap(size, size)
        self._downArrow = down = QtGui.QPixmap(size, size)
        points = (0.4, 0.4, 0.8), (0.2, 0.8, 0.5)

        for arrow, pts in zip((right, down), (points, points[::-1])):
            arrow.fill(QtCore.Qt.transparent)
            polygon = QtGui.QPolygonF(
                [QtCore.QPointF(size*x, size*y) for x, y in zip(*pts)])

            painter = QtGui.QPainter(arrow)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor('#454545'))
            painter.drawPolygon(polygon)

    def _is_folded(self, line):
        block = self.parent().document().findBlockByNumber(line)
        return block.isValid() and block.isVisible()

    def _move_cursor_visible(self):
        cursor = self.parent().textCursor()
        if not cursor.block().isVisible():
            cursor.setVisualNavigation(True)
            cursor.movePosition(QtGui.QTextCursor.Up)
            self.parent().setTextCursor(cursor)

    def code_folding_event(self, lineNumber):
        if self._is_folded(lineNumber):
            self._fold(lineNumber)
        else:
            self._unfold(lineNumber)
        self._move_cursor_visible()

    def _fold(self, lineNumber):
        doc = self.parent().document()
        start = doc.findBlockByNumber(lineNumber - 1)
        end = self._find_fold_closing(start)
        startPos, endPos = start.position(), end.position()

        block = start.next()
        while block.isValid() and block != end:
            block.setVisible(False)
            block.setLineCount(0)
            block = block.next()

        self._foldedBlocks.add(start.blockNumber())
        doc.markContentsDirty(startPos, endPos-startPos)
        layout = doc.documentLayout()
        layout.documentSizeChanged.emit(layout.documentSize())

    def _unfold(self, lineNumber):
        doc = self.parent().document()
        start = doc.findBlockByNumber(lineNumber - 1)
        end = self._find_fold_closing(start)
        startPos, endPos = start.position(), end.position()

        block = start.next()
        while block.isValid() and block != end:
            block.setVisible(True)
            block.setLineCount(block.layout().lineCount())
            endPos = block.position()+block.length()
            if block.blockNumber() in self._foldedBlocks:
                block = self._find_fold_closing(block)
            else:
                block = block.next()

        self._foldedBlocks.remove(start.blockNumber())
        doc.markContentsDirty(startPos, endPos-startPos)
        layout = doc.documentLayout()
        layout.documentSizeChanged.emit(layout.documentSize())

    def _get_leading_spaces(self, line):
        space = self._patIdent.match(line)
        if space is not None:
            return space.group()
        else:
            return ''

    def _find_fold_closing(self, block):
        text = block.text()
        pat = re.compile('(\s)*#begin-fold:')
        if pat.match(text):
            return self._find_fold_closing_label(block)

        spaces = self._get_leading_spaces(text)
        pat = re.compile('^\s*$|^\s*#')
        block = block.next()
        while block.isValid():
            t2 = block.text()
            if not pat.match(t2):
                spacesEnd = self._get_leading_spaces(t2)
                if len(spacesEnd) <= len(spaces):
                    if pat.match(block.previous().text()):
                        return block.previous()
                    else:
                        return block
            block = block.next()
        return block.previous()

    def _find_fold_closing_label(self, block):
        text = block.text()
        label = text.split(':')[1]
        block = block.next()
        pat = re.compile('\s*#end-fold:'+label)
        while block.isValid():
            if pat.match(block.text()):
                return block.next()
            block = block.next()
        return block

    def _hide_symbols(self):
        self._drawSymbols = False

    def enterEvent(self, event):
        self._anim.setDirection(QtCore.QAbstractAnimation.Forward)
        self._anim.start()

    def leaveEvent(self, event):
        self._anim.setDirection(QtCore.QAbstractAnimation.Backward)
        self._anim.start()

    def set_opacity(self, val):
        if val == 0: self._drawSymbols = False
        else: self._drawSymbols = True
        self._opacity = val
        self.update()

    opacity = QtCore.Property(float, fget=lambda self: self._opacity, fset=set_opacity)

    def fontMetrics(self):
        # QWidget's fontMetrics method does not provide an up to date
        # font metrics, just one corresponding to the initial font
        return QtGui.QFontMetrics(self.font)

    def set_font(self, font):
        self.font = font

    def gutter_width(self):
        nlines = max(1, self.parent().blockCount())
        ndigits = max(self.min_char_width,
                      int(math.floor(math.log10(nlines) + 1)))
        width = max(self.fontMetrics().width(u'0' * ndigits) + 3,
                    self.min_width)
        return width+self._fold_area

    def setGeometry(self, rect):
        rect.adjust(0, 0, self._bulge, 0)
        super(LineNumberWidget, self).setGeometry(rect)

    def sizeHint(self):
        return QtCore.QSize(self.gutter_width(), 0)

    def mousePressEvent(self, event):
        cw = self.parent()
        block = cw.firstVisibleBlock()
        cw_offset = cw.contentOffset()
        click_pos = QtCore.QPointF(event.pos())

        while (block.isValid() and not
            cw.blockBoundingGeometry(block).translated(cw_offset).contains(click_pos)):
            block = block.next()

        if self._pat.match(str(block.text())):
            self.code_folding_event(block.blockNumber()+1)

    def paintEvent(self, event):
        """ Paint the line numbers and other gutters
        """
        bulge = self._bulge
        painter = QtGui.QPainter(self)
        painter.setFont(self.font)
        painter.fillRect(event.rect().adjusted(0,0,-bulge,0), self.background_color)

        cw = self.parent()

        curr_block = cw.textCursor().block()
        curr_block_color = cw.line_highlight_color

        cw_offset = cw.contentOffset()
        leading = self.fontMetrics().leading()

        block = cw.firstVisibleBlock()
        blocknum = block.blockNumber()
        geometry = cw.blockBoundingGeometry(block).translated(cw_offset)
        top = geometry.top()
        bottom = geometry.bottom()
        height = geometry.height()

        width = self.width() - bulge
        fold_point = width - self._fold_area
        arrow = self._arrow_size

        pattern = self._pat
        painter.setPen(self.foreground_color)

        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        darker = self.background_color.darker(110)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if block == curr_block or block.blockNumber() in self._foldedBlocks:
                    if block == curr_block:
                        color = curr_block_color
                    else:
                        color = darker
                    painter.fillRect(QtCore.QRect(0, top, width, height),
                                     color)

                    if block.blockNumber() in self._foldedBlocks:
                        # draw a little bump
                        painter.setPen(QtCore.Qt.NoPen)
                        painter.setBrush(color)
                        painter.drawChord(width-bulge/2, top, bulge, height,
                                          90*16, -180*16)
                        painter.setPen(self.foreground_color)

                if self._drawSymbols:
                    if pattern.match(block.text()):
                        opacity = self._opacity
                        painter.setOpacity(opacity)
                        if block.blockNumber() in self._foldedBlocks:
                            painter.drawPixmap(width-arrow, top, self._rightArrow)
                        else:
                            painter.drawPixmap(width-arrow, top, self._downArrow)
                    else:
                        opacity = 0.85*self._opacity
                    painter.setOpacity(1-opacity)
                    painter.drawText(
                        0, top + leading, fold_point - 2, height,
                        QtCore.Qt.AlignRight|QtCore.Qt.AlignTop, str(blocknum+1))
                    painter.setOpacity(1.0)
                else:
                    painter.drawText(
                        0, top + leading, fold_point - 2, height,
                        QtCore.Qt.AlignRight|QtCore.Qt.AlignTop, str(blocknum+1))

            block = block.next()
            blocknum += 1
            geometry = cw.blockBoundingGeometry(block).translated(cw_offset)
            top = geometry.top()
            bottom = geometry.bottom()
            height = geometry.height()
