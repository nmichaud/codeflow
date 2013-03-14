#
# Canopy product code
#
# (C) Copyright 2011 Enthought, Inc., Austin, TX  
# All right reserved.  
#
# This file is confidential and NOT open source.  Do not distribute.
#

""" Defines syntax highlighters for a number of languages.

NOTE: This code was adapted from the syntax highlighters in Spyder.
"""
# Standard library imports.
import __builtin__
import keyword
import re

# System library imports.
from PySide import QtGui
from CanopyTextEdit import SyntaxHighlighter


class Parenthesis(object):
    OPEN_SET = set("{[(")
    CLOSED_SET = set("}])")
    OPEN_REGEX = re.compile(r'[\{\[\(]')
    CLOSED_REGEX = re.compile(r'[\}\]\)]')

    map = dict((p1, p2) for p1, p2 in ["{}", "}{", "[]", "][", "()", ")("])

    def __init__(self, chr, token, position=-1, is_open=True):
        self.chr = chr 
        self.token = token
        self.position = position
        self.is_open = is_open


class BlockData(QtGui.QTextBlockUserData):

    def __init__(self, error=False):
        super(BlockData, self).__init__()
        self.error = error
        self.state_stack = []
        self.end = False
        self.parentheses = []
        self.code_warnings = []

###############################################################################
# Highlighter base class.
###############################################################################

class Highlighter(SyntaxHighlighter):
    """ The base class for code widget syntax highlighters.

    This class is effectively the null/plain-text highlighter.
    """

    def __init__(self, parent, style=None):
        super(Highlighter, self).__init__(parent)
        self.outlineexplorer_data = {}
        self.style = style

    def highlightBlock(self, text):
        self.setFormat(0, len(text), self.style.normal_)

###############################################################################
# Python highlighter.
###############################################################################

def any(name, alternates):
    """ Return a named group pattern matching list of alternates.
    """
    return "(?P<%s>" % name + "|".join(alternates) + ")"

def make_python_patterns(additional_keywords=[], additional_builtins=[]):
    """ Strongly inspired by idlelib.ColorDelegator.make_pat.
    """
    kw = r"\b" + any("keyword", keyword.kwlist+additional_keywords) + r"\b"
    builtinlist = [str(name) for name in dir(__builtin__)
                   if not name.startswith('_')]+additional_builtins
    builtin = r"\b" + any("builtin", builtinlist) + r"\b"
    comment = any("comment", [r"#[^\n]*"])
    instance = any("instance", [r"\bself\b"])
    number = any("number",
                 [r"\b[+-]?[0-9]+[lL]?\b",
                  r"\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b",
                  r"\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b"])
    sqstring =     r"(\b[rRuU])?'[^'\\\n]*(\\.[^'\\\n]*)*'?"
    dqstring =     r'(\b[rRuU])?"[^"\\\n]*(\\.[^"\\\n]*)*"?'
    uf_sqstring =  r"(\b[rRuU])?'[^'\\\n]*(\\.[^'\\\n]*)*(\\)$(?!')$"
    uf_dqstring =  r'(\b[rRuU])?"[^"\\\n]*(\\.[^"\\\n]*)*(\\)$(?!")$'
    sq3string =    r"(\b[rRuU])?'''[^'\\]*((\\.|'(?!''))[^'\\]*)*(''')?"
    dq3string =    r'(\b[rRuU])?"""[^"\\]*((\\.|"(?!""))[^"\\]*)*(""")?'
    uf_sq3string = r"(\b[rRuU])?'''[^'\\]*((\\.|'(?!''))[^'\\]*)*(\\)?(?!''')$"
    uf_dq3string = r'(\b[rRuU])?"""[^"\\]*((\\.|"(?!""))[^"\\]*)*(\\)?(?!""")$'
    paren        = any("paren", [r'([{}\(\)\[\]])'])
    string = any("string", [sq3string, dq3string, sqstring, dqstring])
    ufstring1 = any("uf_sqstring", [uf_sqstring])
    ufstring2 = any("uf_dqstring", [uf_dqstring])
    ufstring3 = any("uf_sq3string", [uf_sq3string])
    ufstring4 = any("uf_dq3string", [uf_dq3string])
    return "|".join([instance, kw, builtin, comment, paren,
                     ufstring1, ufstring2, ufstring3, ufstring4, string,
                     number, any("SYNC", [r"\n"])])

class OutlineExplorerData(object):
    
    CLASS, FUNCTION, STATEMENT, COMMENT = range(4)
    
    def __init__(self):
        self.text = None
        self.fold_level = None
        self.def_type = None
        self.def_name = None
        
    def is_not_class_nor_function(self):
        return self.def_type not in (self.CLASS, self.FUNCTION)
    
    def is_comment(self):
        return self.def_type == self.COMMENT
        
    def get_class_name(self):
        if self.def_type == self.CLASS:
            return self.def_name
        
    def get_function_name(self):
        if self.def_type == self.FUNCTION:
            return self.def_name
    
class PythonHighlighter(Highlighter):
    """ A highlighter for Python scripts.
    """
    # Syntax highlighting rules:
    PROG = re.compile(make_python_patterns(), re.S)
    IDPROG = re.compile(r"\s+(\w+)", re.S)
    ASPROG = re.compile(r".*?\b(as)\b")
    
    # Syntax highlighting states (from one text block to another):
    (NORMAL, INSIDE_SQ3STRING, INSIDE_DQ3STRING,
     INSIDE_SQSTRING, INSIDE_DQSTRING) = range(5)
    DEF_TYPES = {"def": OutlineExplorerData.FUNCTION,
                 "class": OutlineExplorerData.CLASS}
    
    def __init__(self, parent, style=None):
        super(PythonHighlighter, self).__init__(parent, style)
        self.import_statements = {}

    def highlightBlock(self, text):
        style = self.style
        text = unicode(text)
        prev_state = self.previousBlockState()
        if prev_state == self.INSIDE_DQ3STRING:
            offset = -4
            text = r'""" '+text
        elif prev_state == self.INSIDE_SQ3STRING:
            offset = -4
            text = r"''' "+text
        elif prev_state == self.INSIDE_DQSTRING:
            offset = -2
            text = r'" '+text
        elif prev_state == self.INSIDE_SQSTRING:
            offset = -2
            text = r"' "+text
        else:
            offset = 0
            prev_state = self.NORMAL
        
        oedata = None
        import_stmt = None

        self.setFormat(0, len(text), style.normal_)
        
        blockData = None #self.currentBlockUserData()
        if blockData:
            blockData.parentheses = []
        else:
            blockData = BlockData()
            #self.setCurrentBlockUserData(blockData)
        
        state = self.NORMAL
        match = self.PROG.search(text)
        while match:
            for key, value in match.groupdict().items():
                if value:
                    start, end = match.span(key)
                    start = max([0, start+offset])
                    end = max([0, end+offset])
                    if key == "uf_sq3string":
                        self.setFormat(start, end-start, style.string_)
                        state = self.INSIDE_SQ3STRING
                    elif key == "uf_dq3string":
                        self.setFormat(start, end-start, style.string_)
                        state = self.INSIDE_DQ3STRING
                    elif key == "uf_sqstring":
                        self.setFormat(start, end-start, style.string_)
                        state = self.INSIDE_SQSTRING
                    elif key == "uf_dqstring":
                        self.setFormat(start, end-start, style.string_)
                        state = self.INSIDE_DQSTRING
                    elif key == "paren":
                        if value in Parenthesis.OPEN_SET:
                            _p = Parenthesis(value, start, is_open=True)
                            blockData.parentheses.append(_p)
                        elif value in Parenthesis.CLOSED_SET:
                            _p = Parenthesis(value, start, is_open=False)
                            blockData.parentheses.append(_p)
                    else:
                        format_ = getattr(style, key + '_')
                        self.setFormat(start, end-start, format_)
                        if key == "comment":
                            if text.lstrip().startswith('#---'):
                                oedata = OutlineExplorerData()
                                oedata.text = unicode(text).strip()
                                oedata.fold_level = start
                                oedata.def_type = OutlineExplorerData.COMMENT
                                oedata.def_name = text.strip()
                        elif key == "keyword":
                            if value in ("def", "class"):
                                match1 = self.IDPROG.match(text, end)
                                if match1:
                                    start1, end1 = match1.span(1)
                                    self.setFormat(start1, end1-start1,
                                                   style.definition_)
                                    oedata = OutlineExplorerData()
                                    oedata.text = unicode(text)
                                    oedata.fold_level = start
                                    oedata.def_type = self.DEF_TYPES[
                                                                unicode(value)]
                                    oedata.def_name = text[start1:end1]
                            elif value in ("elif", "else", "except", "finally",
                                           "for", "if", "try", "while",
                                           "with"):
                                if text.lstrip().startswith(value):
                                    oedata = OutlineExplorerData()
                                    oedata.text = unicode(text).strip()
                                    oedata.fold_level = start
                                    oedata.def_type = \
                                        OutlineExplorerData.STATEMENT
                                    oedata.def_name = text.strip()
                            elif value == "import":
                                import_stmt = text.strip()
                                
                                # color all the "as" words ( on same line, 
                                # except if in a comment; cheap approximation 
                                # to the truth
                                if '#' in text:
                                    endpos = text.index('#')
                                else:
                                    endpos = len(text)
                                while True:
                                    match1 = self.ASPROG.match(text, end,
                                                               endpos)
                                    if not match1:
                                        break
                                    start, end = match1.span(1)
                                    self.setFormat(start, end-start,
                                                   style.keyword_)
                    
            match = self.PROG.search(text, match.end())

        self.setCurrentBlockState(state)
        
        #if oedata is not None:
        #    block_nb = self.currentBlock().blockNumber()
        #    self.outlineexplorer_data[block_nb] = oedata
        #if import_stmt is not None:
        #    block_nb = self.currentBlock().blockNumber()
        #    self.import_statements[block_nb] = import_stmt

    def rehighlight(self):
        self.import_statements = {}
        super(PythonHighlighter, self).rehighlight()

###############################################################################
# Cython highlighter.
###############################################################################

C_TYPES = 'bool char double enum float int long mutable short signed '\
          'struct unsigned void'

class CythonHighlighter(PythonHighlighter):
    """ A highlighter for Cython code.
    """
    ADDITIONAL_KEYWORDS = ["cdef", "ctypedef", "cpdef", "inline", "cimport",
                           "DEF"]
    ADDITIONAL_BUILTINS = C_TYPES.split()
    PROG = re.compile(make_python_patterns(ADDITIONAL_KEYWORDS,
                                           ADDITIONAL_BUILTINS), re.S)
    IDPROG = re.compile(r"\s+([\w\.]+)", re.S)

###############################################################################
# C/C++ highlighter.
###############################################################################

C_KEYWORDS1 = 'and and_eq bitand bitor break case catch const const_cast continue default delete do dynamic_cast else explicit export extern for friend goto if inline namespace new not not_eq operator or or_eq private protected public register reinterpret_cast return sizeof static static_cast switch template throw try typedef typeid typename union using virtual while xor xor_eq'
C_KEYWORDS2 = 'a addindex addtogroup anchor arg attention author b brief bug c class code date def defgroup deprecated dontinclude e em endcode endhtmlonly ifdef endif endlatexonly endlink endverbatim enum example exception f$ file fn hideinitializer htmlinclude htmlonly if image include ingroup internal invariant interface latexonly li line link mainpage name namespace nosubgrouping note overload p page par param post pre ref relates remarks return retval sa section see showinitializer since skip skipline subsection test throw todo typedef union until var verbatim verbinclude version warning weakgroup'
C_KEYWORDS3 = 'asm auto class compl false true volatile wchar_t'

def make_generic_c_patterns(keywords, builtins):
    """ Strongly inspired by idlelib.ColorDelegator.make_pat.
    """
    kw = r"\b" + any("keyword", keywords.split()) + r"\b"
    builtin = r"\b" + any("builtin", builtins.split()+C_TYPES.split()) + r"\b"
    comment = any("comment", [r"//[^\n]*"])
    comment_start = any("comment_start", [r"\/\*"])
    comment_end = any("comment_end", [r"\*\/"])
    instance = any("instance", [r"\bthis\b"])
    number = any("number",
                 [r"\b[+-]?[0-9]+[lL]?\b",
                  r"\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b",
                  r"\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b"])
    sqstring = r"(\b[rRuU])?'[^'\\\n]*(\\.[^'\\\n]*)*'?"
    dqstring = r'(\b[rRuU])?"[^"\\\n]*(\\.[^"\\\n]*)*"?'
    string = any("string", [sqstring, dqstring])
    define = any("define", [r"#[^\n]*"])
    return "|".join([instance, kw, comment, string, number,
                     comment_start, comment_end, builtin,
                     define, any("SYNC", [r"\n"])])

def make_cpp_patterns():
    return make_generic_c_patterns(C_KEYWORDS1+' '+C_KEYWORDS2, C_KEYWORDS3)

class CppHighlighter(Highlighter):
    """ A highlighter for C/C++ code.
    """
    # Syntax highlighting rules:
    PROG = re.compile(make_cpp_patterns(), re.S)

    # Syntax highlighting states (from one text block to another):
    NORMAL = 0
    INSIDE_COMMENT = 1

    def highlightBlock(self, text):
        style = self.style
        inside_comment = self.previousBlockState() == self.INSIDE_COMMENT
        self.setFormat(0, len(text),
                       style.comment_ if inside_comment else style.normal_)
        
        match = self.PROG.search(text)
        index = 0
        while match:
            for key, value in match.groupdict().items():
                if value:
                    start, end = match.span(key)
                    index += end-start
                    if key == "comment_start":
                        inside_comment = True
                        self.setFormat(start, len(text)-start, style.comment_)
                    elif key == "comment_end":
                        inside_comment = False
                        self.setFormat(start, end-start, style.comment_)
                    elif inside_comment:
                        self.setFormat(start, end-start, style.comment_)
                    elif key == "define":
                        self.setFormat(start, end-start, style.number_)
                    else:
                        format_ = getattr(style, key + '_')
                        self.setFormat(start, end-start, format_)

            # If we're inside a comment, we have to worry about single and
            # double quotes swallowing the comment terminator.
            start = match.start() + 1 if inside_comment else match.end()
            match = self.PROG.search(text, start)

        last_state = self.INSIDE_COMMENT if inside_comment else self.NORMAL
        self.setCurrentBlockState(last_state)

###############################################################################
# Fortran highlighter.
###############################################################################

def make_fortran_patterns():
    "Strongly inspired by idlelib.ColorDelegator.make_pat"
    kwstr = 'access action advance allocatable allocate apostrophe assign assignment associate asynchronous backspace bind blank blockdata call case character class close common complex contains continue cycle data deallocate decimal delim default dimension direct do dowhile double doubleprecision else elseif elsewhere encoding end endassociate endblockdata enddo endfile endforall endfunction endif endinterface endmodule endprogram endselect endsubroutine endtype endwhere entry eor equivalence err errmsg exist exit external file flush fmt forall form format_ formatted function go goto id if implicit in include inout integer inquire intent interface intrinsic iomsg iolength iostat kind len logical module name named namelist nextrec nml none nullify number only open opened operator optional out pad parameter pass pause pending pointer pos position precision print private program protected public quote read readwrite real rec recl recursive result return rewind save select selectcase selecttype sequential sign size stat status stop stream subroutine target then to type unformatted unit use value volatile wait where while write'
    bistr1 = 'abs achar acos acosd adjustl adjustr aimag aimax0 aimin0 aint ajmax0 ajmin0 akmax0 akmin0 all allocated alog alog10 amax0 amax1 amin0 amin1 amod anint any asin asind associated atan atan2 atan2d atand bitest bitl bitlr bitrl bjtest bit_size bktest break btest cabs ccos cdabs cdcos cdexp cdlog cdsin cdsqrt ceiling cexp char clog cmplx conjg cos cosd cosh count cpu_time cshift csin csqrt dabs dacos dacosd dasin dasind datan datan2 datan2d datand date date_and_time dble dcmplx dconjg dcos dcosd dcosh dcotan ddim dexp dfloat dflotk dfloti dflotj digits dim dimag dint dlog dlog10 dmax1 dmin1 dmod dnint dot_product dprod dreal dsign dsin dsind dsinh dsqrt dtan dtand dtanh eoshift epsilon errsns exp exponent float floati floatj floatk floor fraction free huge iabs iachar iand ibclr ibits ibset ichar idate idim idint idnint ieor ifix iiabs iiand iibclr iibits iibset iidim iidint iidnnt iieor iifix iint iior iiqint iiqnnt iishft iishftc iisign ilen imax0 imax1 imin0 imin1 imod index inint inot int int1 int2 int4 int8 iqint iqnint ior ishft ishftc isign isnan izext jiand jibclr jibits jibset jidim jidint jidnnt jieor jifix jint jior jiqint jiqnnt jishft jishftc jisign jmax0 jmax1 jmin0 jmin1 jmod jnint jnot jzext kiabs kiand kibclr kibits kibset kidim kidint kidnnt kieor kifix kind kint kior kishft kishftc kisign kmax0 kmax1 kmin0 kmin1 kmod knint knot kzext lbound leadz len len_trim lenlge lge lgt lle llt log log10 logical lshift malloc matmul max max0 max1 maxexponent maxloc maxval merge min min0 min1 minexponent minloc minval mod modulo mvbits nearest nint not nworkers number_of_processors pack popcnt poppar precision present product radix random random_number random_seed range real repeat reshape rrspacing rshift scale scan secnds selected_int_kind selected_real_kind set_exponent shape sign sin sind sinh size sizeof sngl snglq spacing spread sqrt sum system_clock tan tand tanh tiny transfer transpose trim ubound unpack verify'
    bistr2 = 'cdabs cdcos cdexp cdlog cdsin cdsqrt cotan cotand dcmplx dconjg dcotan dcotand decode dimag dll_export dll_import doublecomplex dreal dvchk encode find flen flush getarg getcharqq getcl getdat getenv gettim hfix ibchng identifier imag int1 int2 int4 intc intrup invalop iostat_msg isha ishc ishl jfix lacfar locking locnear map nargs nbreak ndperr ndpexc offset ovefl peekcharqq precfill prompt qabs qacos qacosd qasin qasind qatan qatand qatan2 qcmplx qconjg qcos qcosd qcosh qdim qexp qext qextd qfloat qimag qlog qlog10 qmax1 qmin1 qmod qreal qsign qsin qsind qsinh qsqrt qtan qtand qtanh ran rand randu rewrite segment setdat settim system timer undfl unlock union val virtual volatile zabs zcos zexp zlog zsin zsqrt'
    kw = r"\b" + any("keyword", kwstr.split()) + r"\b"
    builtin = r"\b" + any("builtin", bistr1.split()+bistr2.split()) + r"\b"
    comment = any("comment", [r"\![^\n]*"])
    number = any("number",
                 [r"\b[+-]?[0-9]+[lL]?\b",
                  r"\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b",
                  r"\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b"])
    sqstring = r"(\b[rRuU])?'[^'\\\n]*(\\.[^'\\\n]*)*'?"
    dqstring = r'(\b[rRuU])?"[^"\\\n]*(\\.[^"\\\n]*)*"?'
    string = any("string", [sqstring, dqstring])
    return "|".join([kw, comment, string, number, builtin,
                     any("SYNC", [r"\n"])])

class FortranHighlighter(Highlighter):
    """ A highlighter for Fortran code.
    """
    # Syntax highlighting rules:
    PROG = re.compile(make_fortran_patterns(), re.I | re.S)
    IDPROG = re.compile(r"\s+(\w+)", re.I | re.S)
    
    # Syntax highlighting states (from one text block to another):
    NORMAL = 0
    
    def highlightBlock(self, text):
        style = self.style
        self.setFormat(0, len(text), style.normal_)
        
        match = self.PROG.search(text)
        index = 0
        while match:
            for key, value in match.groupdict().items():
                if value:
                    start, end = match.span(key)
                    index += end-start
                    format_ = getattr(style, key + '_')
                    self.setFormat(start, end-start, format_)
                    if value in ("subroutine", "module", "function"):
                        match1 = self.IDPROG.match(text, end)
                        if match1:
                            start1, end1 = match1.span(1)
                            self.setFormat(start1, end1-start1,
                                           style.definition_)
                    
            match = self.PROG.search(text, match.end())

class Fortran77Highlighter(FortranHighlighter):
    """ A highlighter for Fortran 77 code.
    """
    
    def highlightBlock(self, text):
        style = self.style
        if text and text[0] in ("*", "c", "C"):
            self.setFormat(0, len(text), style.comment_)
        else:
            super(Fortran77Highlighter, self).highlightBlock(text)
            self.setFormat(0, 5, style.comment_)
            self.setFormat(73, max([73, len(text)]), style.comment_)
