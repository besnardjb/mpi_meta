from mpiiface import MPI_Interface, MPI_Standard_meta

a = MPI_Interface("./prepass.dat", MPI_Standard_meta(lang="c", fprefix=""))


def gen_c_iface(f):
	print("\n")
	print("/*{}*/".format(f.name()))
	print(f.doxygen())
	print("{};".format(f.proto()))
	print("{};".format(f.proto(prefix="P")))



def is_part_of_bindings(f):
    return f.isbindings() and \
        f.isc() and \
		not f.iscallback() and \
        not f.isf08conv()


a.forall(gen_c_iface, is_part_of_bindings)
