#
# Canopy product code
#
# (C) Copyright 2011 Enthought, Inc., Austin, TX  
# All right reserved.  
#
# This file is confidential and NOT open source.  Do not distribute.
#

# Standard library imports.
import sys

# System library imports.
from PySide import QtGui

# Enthought library imports.
from traits.api import Bool, Color, Font, HasStrictTraits, HasTraits, \
     Instance, on_trait_change

# Pygments imports.
from pygments.styles import get_style_by_name

###############################################################################
# Style base classes.
###############################################################################

class TextStyle(HasStrictTraits):
    """ A style for a text fragment.
    """
    color = Color('black')
    bold = Bool(False)
    italic = Bool(False)

class TextStyleTrait(Instance):
    """ A mapped TextStyle -> QTextCharFormat trait.
    """
    is_mapped = True

    def __init__(self, **kwds):
        super(TextStyleTrait, self).__init__(
            TextStyle, has_text_char_format=True, **kwds)

    def mapped_value(self, value):
        format = QtGui.QTextCharFormat()
        format.setForeground(value.color)
        if value.bold:
            format.setFontWeight(QtGui.QFont.Bold)
        format.setFontItalic(value.italic)
        return format

    def post_setattr(self, object, name, value):
        object.__dict__[name + '_'] = self.mapped_value(value)

class CodeStyle(HasTraits):
    """ A style for the code editor.
    """

    font = Font()

    background = Color('white')
    current_line = Color()
    occurrence = Color()
    gutters = Color()
    matched_paren = Color()
    unmatched_paren = Color()

    normal = TextStyleTrait()
    keyword = TextStyleTrait()
    builtin = TextStyleTrait()
    definition = TextStyleTrait()
    comment = TextStyleTrait()
    string = TextStyleTrait()
    number = TextStyleTrait()
    instance = TextStyleTrait()

    info = Color('limegreen')
    warning = Color('orange')
    error = Color('red')

    def __init__(self, **traits):
        super(CodeStyle, self).__init__(**traits)
        for name, trait in self.traits(has_text_char_format=True).iteritems():
            # FIXME: Work around Traits bug. 'post_setattr' is not being called.
            trait.post_setattr(self, name, getattr(self, name))
        self._update_formats()

    def _font_default(self):
        # Set a decent fixed width font for this platform.
        font = QtGui.QFont()
        if sys.platform == 'win32':
            # Prefer Consolas, but fall back to Courier if necessary.
            font.setFamily('Consolas')
            if not font.exactMatch():
                font.setFamily('Courier')
        elif sys.platform == 'darwin':
            font.setFamily('Monaco')
        else:
            font.setFamily('Monospace')
        font.setStyleHint(QtGui.QFont.TypeWriter)
        return font

    @on_trait_change('background, font')
    def _update_formats(self):
        if self.traits_inited():
            for name in self.trait_names(has_text_char_format=True):
                format = getattr(self, name + '_')
                format.setFont(self.font)
                format.setBackground(self.background)
                
    # FIXME: Add some dynamicness to this using getattr or something else.
    def get_style_for_token(self, token):
        return self.normal

###############################################################################
# Predefined styles.
###############################################################################

class EmacsStyle(CodeStyle):

    background = "#000000"
    current_line = "#2b2b43"
    occurrence = "#abab67"
    gutters = "#555555"
    matched_paren = "#009800"
    unmatched_paren = "#c80000"

    normal = TextStyle(color="#ffffff")
    keyword = TextStyle(color="#3c51e8")
    builtin = TextStyle(color="#900090")
    definition = TextStyle(color="#ff8040", bold=True)
    comment = TextStyle(color="#005100")
    string = TextStyle(color="#00aa00", italic=True)
    number = TextStyle(color="#800000")
    instance = TextStyle(color="#ffffff", italic=True)

class IdleStyle(CodeStyle):

    background = "#ffffff"
    current_line = "#eeffdd"
    occurrence = "#e8f2fe"
    gutters = "#efefef"
    matched_paren = "#99ff99"
    unmatched_paren = "#ff9999"

    normal = TextStyle(color="#000000")
    keyword = TextStyle(color="#ff7700", bold=True)
    builtin = TextStyle(color="#900090")
    definition = TextStyle(color="#0000ff")
    comment = TextStyle(color="#dd0000", italic=True),
    string = TextStyle(color="#00aa00")
    number = TextStyle(color="#924900")
    instance = TextStyle(color="#777777", bold=True, italic=True)
    
class ScintillaStyle(CodeStyle):

    background = "#ffffff"
    current_line = "#eeffdd"
    occurrence = "#ffff99"
    gutters = "#efefef"
    matched_paren = "#99ff99"
    unmatched_paren = "#ff9999"

    normal = TextStyle(color="#000000")
    keyword = TextStyle(color="#00007f", bold=True)
    builtin = TextStyle(color="#000000")
    definition = TextStyle(color="#007f7f", bold=True)
    comment = TextStyle(color="#007f00")
    string = TextStyle(color="#7f007f")
    number = TextStyle(color="#007f7f")
    instance = TextStyle(color="#000000", italic=True)

class IPythonStyle(CodeStyle):
    """Adapted from the default style of Pygments, which IPython uses.
    """

    background = "#ffffff"
    current_line = "#eeffdd"
    occurrence = "#ffff99"
    gutters = "#efefef"
    matched_paren = "#99ff99"
    unmatched_paren = "#ff9999"

    normal = TextStyle(color="#000000")
    keyword = TextStyle(color="#008000", bold=True)
    builtin = TextStyle(color="#008000")
    definition = TextStyle(color="#0000ff", bold=True)
    comment = TextStyle(color="#408080", italic=True)
    string = TextStyle(color="#BA2121")
    number = TextStyle(color="#666666")
    instance = TextStyle(color="#000000", italic=True)

class PygmentsStyle(IPythonStyle):
    """A adapter for using Pygments style classes in Canopy.
    """
    # FIXME: initialize the few attributes concerning to the editor from the
    # pygments styles like background, matched_paren, unmatched_paren, etc.
    def __init__(self, style=None, **traits):
        if style is None:
            self.style = get_style_by_name('default')
        else:
            self.style = get_style_by_name(style)
        
        if hasattr(self.style, 'background_color'):
            self.background = self.style.background_color
        
        if hasattr(self.style, 'highlight_color'):
            self.current_line = self.style.highlight_color
        
        self._formats = {}
        self._brushes = {}
        super(CodeStyle, self).__init__(**traits)
    
    def get_style_for_token(self, token):
        """ Returns a QTextCharFormat for token or None.
        """
        if token in self._formats:
            return self._formats[token]
        result = None
        try:
            pygments_style = self.style.style_for_token(token)
        except KeyError:
            # Can happen if user manually selects wrong lexer for file.
            pygments_style = {}
        for key, value in pygments_style.items():
            if value:
                if result is None:
                    result = QtGui.QTextCharFormat()
                if key == 'color':
                    result.setForeground(self._get_brush(value))
                elif key == 'bgcolor':
                    result.setBackground(self._get_brush(value))
                elif key == 'bold':
                    result.setFontWeight(QtGui.QFont.Bold)
                elif key == 'italic':
                    result.setFontItalic(True)
                elif key == 'underline':
                    result.setUnderlineStyle(
                        QtGui.QTextCharFormat.SingleUnderline)
                elif key == 'sans':
                    result.setFontStyleHint(QtGui.QFont.SansSerif)
                elif key == 'roman':
                    result.setFontStyleHint(QtGui.QFont.Times)
                elif key == 'mono':
                    result.setFontStyleHint(QtGui.QFont.TypeWriter)
                elif key == 'border':
                    # Borders are normally used for errors. We can't do a border
                    # so instead we do a wavy underline
                    result.setUnderlineStyle(
                        QtGui.QTextCharFormat.WaveUnderline)
                    result.setUnderlineColor(self._get_color(value))
        self._formats[token] = result
        return result

    def _get_brush(self, color):
        """ Returns a brush for the color.
        """
        result = self._brushes.get(color)
        if result is None:
            qcolor = self._get_color(color)
            result = QtGui.QBrush(qcolor)
            self._brushes[color] = result

        return result

    def _get_color(self, color):
        qcolor = QtGui.QColor()
        qcolor.setRgb(int(color[:2],base=16),
                      int(color[2:4], base=16),
                      int(color[4:6], base=16))
        return qcolor
