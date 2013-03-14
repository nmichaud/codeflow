#!/usr/bin/env python

############################################################################
##
## Copyright (C) 2006-2006 Trolltech ASA. All rights reserved.
##
## This file is part of the example classes of the Qt Toolkit.
##
## Licensees holding a valid Qt License Agreement may use this file in
## accordance with the rights, responsibilities and obligations
## contained therein.  Please consult your licensing agreement or
## contact sales@trolltech.com if any conditions of this licensing
## agreement are not clear to you.
##
## Further information about Qt licensing is available at:
## http://www.trolltech.com/products/qt/licensing.html or by
## contacting info@trolltech.com.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################

import math, sys

from PySide import QtCore, QtGui

class InfiniteCanvas(QtGui.QGraphicsView):
    def __init__(self, *args, **kw):
        super(InfiniteCanvas, self).__init__(*args, **kw)

        self.setTransformationAnchor(QtGui.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtGui.QGraphicsView.AnchorViewCenter)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setCacheMode(QtGui.QGraphicsView.CacheBackground)
        self.setViewportUpdateMode(QtGui.QGraphicsView.BoundingRectViewportUpdate)
        self.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QtGui.QGraphicsView.FullViewportUpdate)
        bounds = sys.maxint / 2
        self.setSceneRect(QtCore.QRectF(-bounds, -bounds,sys.maxint,sys.maxint))

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.AltModifier:
            self.scaleView(math.pow(2.0, -event.delta() / 240.0))
        else:
            super(InfiniteCanvas, self).wheelEvent(event)

    def scaleView(self, scaleFactor):
        factor = self.matrix().scale(scaleFactor, scaleFactor).mapRect(QtCore.QRectF(0,0,1,1)).width()

        if factor < 0.4 or factor > 1:
            return

        self.scale(scaleFactor, scaleFactor)

if __name__ == '__main__':

    app = QtGui.QApplication(sys.argv)

    scene = QtGui.QGraphicsScene()

    view = InfiniteCanvas(scene)
    view.setWindowTitle("Code Canvas")
    view.resize(400, 300)
    view.show()

    sys.exit(app.exec_())
