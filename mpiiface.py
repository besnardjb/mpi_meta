import json
import copy
from bindingtypes import BIG_C_KIND_MAP, SMALL_C_KIND_MAP

class MPI_Standard_meta():

    def __init__(self, lang="std", fprefix="", fsuffix="", mpi_version="4.0.0"):
        varray = [int(c) for c in mpi_version.split(".") ]
        self._std2ckindmap = BIG_C_KIND_MAP if varray[0] >= 4 else SMALL_C_KIND_MAP
        self.lang = lang
        self.fprefix = fprefix
        self.fsuffix = fsuffix

    def fname(self, name):
        return self.fprefix + name + self.fsuffix

    def _kind_expand_c(self, kind):
        if kind in self._std2ckindmap:
            return self._std2ckindmap[kind]
        else:
            return "ERR"

    def kind_expand(self, kind):
        if self.lang == "std":
            return kind
        elif self.lang == "c" or self.lang == "fbind":
            return self._kind_expand_c(kind)
        else:
            raise Exception("No such kind expand")


class MPI_Parameter():

    def __init__(self, content, meta=None):
        self.meta = meta
        self.content = content.copy()
        self.fbind_type = None
        self.fbind_noderef = False
        self.fbind_getref=False

    def _get_attr(self, attr):
        if attr in self.content:
            return self.content[attr]
        else:
            return None

    def set_extern_fbind_type(self, type):
        self.fbind_type = type

    def ishandle(self):
        handle_kind = ["INFO",
                       "STATUS",
                       "REQUEST",
                       "OPERATION",
                       "DATATYPE",
                       "GROUP",
                       "WINDOW",
                       "FILE",
                       "ERRHANDLER",
                       "COMMUNICATOR"]
        return self.kind() in handle_kind

    def pointer(self):
        return self._get_attr("pointer")

    def length(self):
        return self._get_attr("length")

    def array_length(self):
        return isinstance(self._get_attr("length"), list)

    def _get_c_pointer(self):

        if self.meta.lang != "c" and self.meta.lang != "fbind":
            return ''

        if self.pointer() is not None and not self.pointer():
            return ''

        if self.kind() == 'STRING_2DARRAY':
            return '**'

        if self.kind() == 'ARGUMENT_LIST':
            return '***'

        # needed for MPI_UNPACK_EXTERNAL[_size]
        if (self.kind() == 'STRING' and
            self.length() == '*' and
                not self.pointer()):
            return ''

        if self.kind() in ('BUFFER', 'C_BUFFER', 'C_BUFFER2', 'C_BUFFER3',
                                    'C_BUFFER4', 'STRING', 'EXTRA_STATE',
                                    'EXTRA_STATE2', 'ATTRIBUTE_VAL', 'STATUS',
                                    'ATTRIBUTE_VAL_10', 'STRING_ARRAY',
                                    'FUNCTION', 'FUNCTION_SMALL', 'POLYFUNCTION',
                                    'TOOL_MPI_OBJ', 'F08_STATUS', 'F90_STATUS'):
            return '*'

        if (self.content['param_direction'] == 'inout' or
                self.content['param_direction'] == 'out' or
                self.content['pointer']) and self.content['length'] is None:
            return '*'

        return ''

    def get_c_array(self):
        if self.meta.lang != "c" and self.meta.lang != "fbind":
            return ''
        # Add "[]" if:
        # - This is not a STRING, and
        # - length > 0, and
        # - "pointer" was not specified
        # OR
        # - The type is STRING_ARRAY or STRING_2DARRAY

        if self.kind() == 'C_BUFFER4':
            # length set on MPI_User_function
            return ''

        if ( self.kind() != 'STRING' and
                self.length() is not None and
                not isinstance(self.length(), list) and
                not self.pointer()):
            return '[]'

        # required by MPI_UNPACK_EXTERNAL, it uses array notation for a string.
        if ( self.kind()  == 'STRING' and
                self.length() == '*' and
                not self.pointer()):
            return '[]'

        if ( self.kind()  == 'STRING_ARRAY' or
                 self.kind()  == 'STRING_2DARRAY'):
            return '[]'

        # As of MPI-4.0, we have array parameters with -- at most -- 2
        # dimensions.  Always print the first dimension as [] (above).
        # If we have a second dimension, print it (e.g.,
        # MPI_GROUP_RANGE_INCL & EXCL).
        if isinstance(self.length(), list):
            return '[][{len}]'.format(len=self.length()[1])

        return ''

    def fbindpointer(self):
        return "*" if (not self._get_c_pointer() and not self.get_c_array()) else ""

    def setfbindnoderef(self):
         self.fbind_noderef=True

    def setfbindgetref(self):
         self.fbind_getref=True

    def desc(self):
        return self._get_attr("desc")

    def intent(self):
        return self._get_attr("param_direction")

    def isout(self):
        intent = self.intent()
        if intent:
            return intent.endswith("out")

    def isin(self):
        intent = self.intent()
        if intent:
            return intent.startswith("in")

    def constant(self):
        return self._get_attr("constant")

    def kind_expand(self):
        if (self.kind() == "FUNCTION") or (self.kind() == "FUNCTION_SMALL") or self.kind() == "POLYFUNCTION":
            return self._get_attr("func_type")
        else:
            return self.meta.kind_expand(self.kind())

    def type_c(self, noconst=False):
        return ("const " if self.constant() and not noconst else "") + self.kind_expand()

    def type_full_c(self):
        return "{}{}{}".format( self.type_c(),
                                 self._get_c_pointer(),
                                 self.get_c_array())

    def type_c_is_pointer(self):
        return (self._get_c_pointer() == "*")

    def str_c(self):
        return "{} {}{}{}".format( self.type_c(),
                                   self._get_c_pointer(),
                                   self.name(),
                                   self.get_c_array())

    def str_fbind(self):
        
        if self.fbind_type:
            # Was type temporarilly overridden ?
            ftype = self.fbind_type
            self.fbind_type = None
        else:
            ftype = self.kind_expand()

        ftype += self.fbindpointer()
        return "{}{} {}{}{}".format("const " if self.constant() else "",
                                    ftype,
                                    self._get_c_pointer(),
                                    self.name(),
                                    self.get_c_array())

    def __str__(self):
        if self.meta.lang == "c":
            return self.str_c()
        elif self.meta.lang == "fbind":
            return self.str_fbind()
        else:
            return "{} {}".format(self.kind(), self.name())

    def doxygen(self):
        return  " * @param {0} {1}".format(self.name(), self.desc()) 

    def kind(self):
        return self._get_attr("kind")

    def name(self):
        if self.kind() == "VARARGS":
            return ""
        return self._get_attr("name")

    def set_name(self, name):
        self.content["name"] = name



class MPI_Function():

    def _register_parameters(self, meta=None):
        self.parameters = []
        if "parameters" in self.content:
            for p in self.content["parameters"]:
                self.parameters.append(MPI_Parameter(p, meta))

    def __init__(self, content, meta=None):
        self.meta = meta
        self.content = content.copy()
        self._register_parameters(meta)

    def params(self):
        if self.meta.lang == "c" or self.meta.lang:
            #No Ierror
            return [ x for x in self.parameters if x.name() != "ierror"]
        else:
            return self.parameters

    def _gen_fbind_paramlist(self):
        # We need to add string suffixes and inline args
        # depending on the fortran support type
        ret = []
        suffix_ret = []
        
        for p in self.parameters:
            if p.kind() == "STRING":
                ret.append("{} CHAR_MIXED(size_{})".format(str(p), p.name()))
                suffix_ret.append("CHAR_END(size_{})".format(p.name()))
            else:
                ret.append(str(p))

        if suffix_ret:
            ret[-1] += " " + " ".join(suffix_ret)

        return ret

    def proto(self, prefix="", suffix="", lowername=False):
        if self.meta.lang == "c":
            str_params = [str(x) for x in self.params()]
        else:
            if self.meta.lang == "fbind":
                str_params = self._gen_fbind_paramlist()
            else:
                str_params = [str(x) for x in self.parameters]

        fname = self.name()
        if lowername:
            fname = fname.lower()

        return "{} {}({})".format(self.meta.kind_expand(self.return_kind()),
                                  prefix + self.meta.fname(fname) + suffix,
                                  ", ".join(str_params))

    def __str__(self):
        return self.proto()

    def _get_attr(self, attr):
        if attr in self.content:
            return self.content[attr]
        else:
            return None

    def isf08conv(self):
        return (self.name().find("f2f08") != -1) or (self.name().find("f082f") != -1)

    def isvariadic(self):
        return len([1 for x in self.parameters if x.kind()=="VARARGS"])


    def _has_ierror(self):
        return len([1 for x in self.parameters if x.name()=="ierror"])

    def return_type(self):
	    return self.meta.kind_expand(self.return_kind())

    def _gen_call_generic(self,
                          param_cb,
                          var = "ret",
                          fprefix="",
                          fsuffix="",
                          rename=None,
                          use_ierror=False,
                          lowername=False):
        if self.return_kind() != "NOTHING":
            has_ret_val = 1

        call=""

        if has_ret_val:
            if use_ierror and self.return_kind() == "ERROR_CODE" and self._has_ierror():
                call += "*ierror = "
            else:
                call+="{} {} = ".format(self.meta.kind_expand(self.return_kind()),
                                    var)

        if rename:
            # Make sure to copy as we edit the array
            loc_params = copy.deepcopy(self.params())
            for p in loc_params:
                name = p.name()
                if name in rename:
                    p.set_name(rename[name])
        else:
            loc_params = self.params()

        str_params = [param_cb(x) for x in loc_params]

        fname = self.meta.fname(self.name())
        if lowername:
            fname = fname.lower()

        call += "{}({});".format(fprefix + fname + fsuffix,
                                 ", ".join(str_params))

        return call

    def _gen_call_c(self, var = "ret", fprefix="", fsuffix="", rename=None, lowername=False):
        def c_param(param):
            return param.name()
        return self._gen_call_generic(c_param, var, fprefix, fsuffix, rename)


    def _gen_call_fbind(self, var = "ret", fprefix="", fsuffix="", rename=None):
        def f_param(param):
                    # We need to add reference to non pointer types
        # and output pointers
            if param.fbind_getref == True:
                ptr = "&"
                param.fbind_getref = False
            elif param.fbind_noderef == True:
                ptr = ""
                param.fbind_noderef = False
            else:
                ptr = param.fbindpointer()
            return ptr + param.name()
        return self._gen_call_generic(f_param, var, fprefix, fsuffix, rename, use_ierror=True)

    def gen_call(self, var="ret", fprefix="", fsuffix="", rename=None):
        if self.meta.lang == "c":
            return self._gen_call_c(var, fprefix, fsuffix, rename)
        elif self.meta.lang == "fbind":
            return self._gen_call_fbind(var, fprefix, fsuffix, rename)
        return ""

    def _gen_return_c(self):
        if self.return_kind() == "NOTHING":
            return ""
        return "return ret;"

    def gen_return(self):
        if self.meta.lang == "c":
            return self._gen_return_c()
        return ""

    def return_kind(self):
        return self._get_attr("return_kind")

    def name(self):
        return self._get_attr("name")

    def iscallback(self):
        attrs = self._get_attr("attributes")
        return attrs["callback"]

    def isbindings(self):
        attrs = self._get_attr("attributes")
        return attrs["lis_expressible"]

    def isf90(self):
        attrs = self._get_attr("attributes")
        return attrs["f90_expressible"]

    def iscallback(self):
        attrs = self._get_attr("attributes")
        return attrs["callback"]


    def isc(self):
        attrs = self._get_attr("attributes")
        return attrs["c_expressible"]

    def isfile(self):
        return self.name().startswith("MPI_File")

    def isdeprecated(self):
        attrs = self._get_attr("attributes")
        return attrs["deprecated"]

    def number_of_buffer_params(self):
        bcnt = [1 for x in self.parameters if x.kind() == "BUFFER"]
        return sum(bcnt)

    def get_param_by_kind(self, kind):
        return [ x for x in self.parameters if x.kind() == kind]

    def iscollective(self):
        coll_names = ["gather", "scatter", "reduce", "bcast", "alltoall", "barrier"]
        lname = self.name().lower()
        for cn in coll_names:
            if cn in lname:
                return 1
        return 0

    def isinit(self):
        return self.name() in ["MPI_Init", "MPI_Init_thread"]

    def doxygen(self):
        brief = "MPI function {}".format(self.name())
        params = "\n".join([x.doxygen() for x in self.params()])
        if not params:
            params = " *"
        returnt = " *"
        returndesc = "\n"
        if self.return_kind() != "NOTHING":
            returnt = " * @return " + self.meta.kind_expand(self.return_kind())
        
        if self.return_kind() == "ERROR_CODE":
            returndesc="MPI_SUCCESS on success other MPI_* error code otherwise"

        return """
/**
 * @brief {0}
 * 
{1}
 *
{2} {3} 
 */""".format(brief, params, returnt, returndesc)

    def forall_params(self, callback, filter_callback=None):
        for p in self.parameters:
            if filter_callback and not filter_callback(p):
                continue
            callback(p)

# Cleang regexpr \\\\[a-z]+\{([^\}]+)\} $1

class MPI_Interface():

    def _load_content(self, f):
        self.standard_content = json.load(f)

    def _load_function(self, meta=None):
        self.functions = {}
        for k, v in self.standard_content.items():
            self.functions[k] = MPI_Function(v, meta)

    def __init__(self, path, meta=MPI_Standard_meta()):
        self.meta = meta
        self._load_content(path)
        self._load_function(meta)

    def forall(self, callback, filter_callback=None):

        # Do some sorting for more elegant output
        func = [ f for f in self.functions.values()]
        func.sort(key=lambda f: f.name())

        for f in func:
            if filter_callback and not filter_callback(f):
                continue
            callback(f)

