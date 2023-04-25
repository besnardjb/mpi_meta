import os
import re
import copy
import random
from ruamel.yaml import YAML
from mpiiface import MPI_Interface, MPI_Standard_meta, MPI_Function, MPI_Parameter

SRCDIR="."
OUTDIR="./tests/"
random_words = open("/usr/share/dict/words","r").read().split()
standards = {}
yaml_handlers = {}

def get_func_standard(s):
    try:
        return min([idx for idx in standards.keys() if s in standards[idx]['add']])
    except ValueError:
            print("WARNING: {} NOT FOUND !".format(s))
            return max(standards.keys())
            

def isascii(s):
    return len(s) == len(s.encode())

def valid(s):
    return ascii(s) and s.lower() not in ["int", "double", "integer", "real", "long"]

def param_counter_by_kind(func, pattern=None):
    return len([param for param in func.params() if not pattern or pattern in param.kind()])

def build_c_code(func, decls, calls):
    code_decls = []
    code_calls = []
    has_ret = False
    params = []
    new_decls = []
    for d in decls:
        varname = d[0]
        param = d[1]
        if not param.isc():
            continue
        if param.kind() == "VARARGS":
            code_decls.append("char* {}[10];".format(varname))
        else:
            code_decls.append("{};".format(param.type_decl_c(varname)))
        params.append(varname)
    
    if func.return_kind() != "NOTHING":
        code_decls.append("{} ret;".format(func.meta.kind_expand(func.return_kind(), lang="c")))
        has_ret = True
    
    for c in calls:
        if has_ret:
            code_calls.append("ret = {}({});".format(c, ", ".join(params)))
        else:
            code_calls.append("(void) {}({});".format(c, ", ".join(params)))
    return """#include <mpi.h>
int main(char argc, char**argv)
{{
    /* vars */
    {}
    /* calls */
    {}
    return 0;
}}
""".format("\n    ".join(code_decls), "\n    ".join(code_calls))


def _build_f_code(func, decls, calls, include=None, lang=None):
    params = []
    has_ret = False
    if not include:
        include = "include 'mpif.h'"

    if not lang:
        lang = "f"
        
    code_decls = []
    code_calls = []
    for d in decls:
        varname = d[0]
        param = d[1]
        params.append(varname)
        code_decls.append("{}".format(param.type_decl_f(varname, lang=lang)))
    
    if func.return_kind() not in ["NOTHING", "ERROR_CODE"]:
        code_decls.append("{} ret".format(func.meta.kind_expand(func.return_kind(), lang=lang)))
        has_ret = True

    for c in calls:
        if has_ret:
            code_calls.append("ret = {}({})".format(c.lower(), ", ".join(params)))
        else:
            code_calls.append("call {}({})".format(c.lower(), ", ".join(params)))
    return """
        program main
        {}
        {}
        {}
        end program main
    """.format(include, "\n       ".join(code_decls), "\n       ".join(code_calls))

def build_f77_code(func, decls, calls):
    new_decls = []
    for idx, value in enumerate(decls):
        name, param = value
        if param.isf():
            new_decls.append(value)
    return _build_f_code(func, new_decls, calls, lang="f90", include= "include 'mpif.h'")

def build_f90_code(func, decls, calls):
    new_decls = []
    for idx, value in enumerate(decls):
        name, param = value
        if param.isf90():
            new_decls.append(value)
    return _build_f_code(func, new_decls, calls, lang="f90", include="use mpi")

def build_f08_code(func, decls, calls):
    new_decls = []
    for idx, value in enumerate(decls):
        name, param = value
        if param.isf08():
            new_decls.append(value)
    return _build_f_code(func, new_decls, calls, lang="f08", include="use mpi_f08")

def dump_code(func, filepath, decls, calls, lang="c"):
    content = ""
    if lang == "c":
        content = build_c_code(func, decls, calls)
    elif lang == "f77":
        content = build_f77_code(func, decls, calls)
    elif lang == "f90":
        content = build_f90_code(func, decls, calls)
    elif lang == 'f08':
        content = build_f08_code(func, decls, calls)
    
    assert (content)
    with open(filepath, "w") as fh:
        fh.write(content)


def dump_yaml(nodename, std, srcfile, tags, lang="c"):
        # then, append to associated YAML
        extra_flags = "-ffree-form" if lang in ['f', 'f77', 'f90'] else ""
        tags.append("std_{}".format(std))
        YAML().dump({"{}".format(nodename): {
                "tag": tags,
                "build": {
                    "files": ["{}".format(srcfile)],
                    "cflags": "-Wno-deprecated-declarations -Werror {}".format(extra_flags)
                }
            }
        }, yaml_handlers["functions/{}".format(std)])

def process_function(func):
    global OUTDIR, yaml_handlers
    if not func.isc():
        return
    # first, create source file
    decls = []
    decls_large = []
    calls = []
    calls_large = []
    std = get_func_standard(func.name())
    large_std = 4
    picked_names = []
    # 4 scenarios (2x2):
    #  - Function has a 'largecount' version -> any 'POLY' param type
    #  - A param is exclusive to the 'largecount' version (large_only is
    #    True)
    # this leads to build the following:
    # (decls,parameters) contains attributes for regular calls
    # (decls_large,parameters_large) contains attributes for largecount
    # calls
    # To generate the 4 scenarios:
    # if func() has a largecount versions:
    #    - decls & func(parameters) (BUT DROP 'large_only' params !)
    #    - decls_large & func_c(parameter_large)
    # if func() doesn't have a largecount version:
    #    - decls & func(parameters)
    #    - *_large lists SHOULDN'T be set as no param should have the 'POLY'
    #      type
    largecount_alternate_func = param_counter_by_kind(func, "POLY") > 0
    i = 0
    for param in func.params(lang='std'):
        varname = "{}_{}".format("var", str(i))
        i += 1
        picked_names.append(varname)
        
        #build the only case where a '_c' function is built with
        # a different set of parameters
        # -> take ALL args (there is no attribute to set parameters that
        # SHOULD NOT be part of largecount prototypes)
        if largecount_alternate_func:
            decls_large.append((varname, param))
       
        #  Now, attenmpt to build two scenarios at once:
        # either (largecount func & not 'large_only' parameter) or not
        # largecount func -> pick up
        if largecount_alternate_func and not param.attr('large_only') or not largecount_alternate_func:
            decls.append((varname, param))
                    
    calls.append("{}".format(func.name()))
    calls.append("P{}".format(func.name()))
    
    if decls_large:
        calls_large.append("{}_c".format(func.name()))
        calls_large.append("P{}_c".format(func.name()))

    srcpath = os.path.join(OUTDIR,
                     "functions",
                     "{}".format(std),
                     "{}".format(func.name())
        )
    
    large_srcpath = os.path.join(OUTDIR,
                     "functions",
                     "{}".format(large_std),
                     "{}_c".format(func.name())
    )
            
    
    comb_list = []
    if func.isc():
        comb_list.append(("c", ".c"))
    if func.isf():
        comb_list.append(("f77", ".f"))
    if func.isf90():
        comb_list.append(("f90", ".f90"))
    if func.isf08():
        comb_list.append(("f08", ".f08"))

    for i in comb_list:
        lang = i[0]
        ext = i[1]
        dump_code(func, srcpath + ext, decls, calls, lang=lang)
        dump_yaml("{}_lang{}".format(func.name(), lang),
                  std, os.path.basename(srcpath + ext),
                  lang=lang, tags=[lang, "functions"])
    
        if largecount_alternate_func:
            dump_code(func, large_srcpath + ext, decls_large, calls_large)
            dump_yaml("{}_c_lang{}".format(func.name(), lang),
                      large_std,
                      os.path.basename(large_srcpath + ext),
                      lang=lang, tags=[lang, 'functions', 'large_count'])


def classify_functions_per_standard():
    
    global SRCDIR, OUTDIR
    
    for d in ["functions"]:
        path = os.path.join(SRCDIR, "classification", d)
        for f in os.listdir(path):
            catch = re.match("functions.(\d).x", f)
            if not catch:
                raise ValueError()
            else:
                std = catch.group(1)    
                target = catch.group(3) if len(catch.groups()) >= 2 else "add"
            
            standards.setdefault(std, {'add': [], 'rm': []})
            
            with open(os.path.join(path, f), 'r') as fh:
                standards[std][target] = (fh.read().strip().split("\n"))
                
            prefix = os.path.join(OUTDIR, d, std)
            os.makedirs(prefix, exist_ok = True)
            #for ext in ['c', 'F', 'f90', 'f08']:
            #    srcfile = os.path.join(os.path.abspath(SRCDIR), d+"."+ext)
            #    dstfile = os.path.join(os.path.abspath(prefix), d+"."+ext)
            #    if not os.path.exists(dstfile):
            #        os.symlink(srcfile, dstfile)
            yaml_handlers["{}/{}".format(d, std)] = open(os.path.join(prefix, "pcvs.yml"), "w")
def is_part_of_bindings(f):
    return f.isbindings() and \
        f.isc() and \
		not f.iscallback()


classify_functions_per_standard()
a = MPI_Interface("./prepass.dat", MPI_Standard_meta(lang="c", mpi_version="4.0.0"))
a.forall(process_function, is_part_of_bindings)