import os
from glob import glob
import json

standards = []

def clean_mpi_name(name):
   lname = name.lower()
   return "MPI_" + lname[4].upper() + lname[5:]

def load_def(file):
   ret = []
   with open(file,"r") as f:
      data = f.read()
      lines = data.split("\n")
      for l in lines:
         ret.append(clean_mpi_name(l))
   return ret


for f in glob("*.dat"):
   name = f.replace(".dat","")
   standards.append(float(name))

standards.sort()
standards = [str(x) for x in standards]

print(standards)


print(clean_mpi_name("MPI_CART_SUB"))

funcs = {}


def is_in_prev_std(ref_std, function):
   prev = standards[:standards.index(ref_std)]
   all_prev_func = set()
   for s in prev:
      if s in funcs:
         all_prev_func.update(funcs[s])

   return function in all_prev_func


for s in standards:
   print("Processing ... {}".format(s))
   fdef = load_def("./{}.dat".format(s))
   ndef = [ x for x in fdef if not is_in_prev_std(s, x)]
   funcs[s] = ndef

print("!!!!!!!!!!!!!!!")
print("STATISTICS !!!!")
print("!!!!!!!!!!!!!!!")

tot = 0
for s in standards:
   tot = tot + len(funcs[s])
   print("{} len {} tot {}".format(s, len(funcs[s]), tot))


standard_labels = {}


for s in standards:
   major = "REV:{}".format(s.split(".")[0])
   std = "STD:{}".format(s)
   for f in funcs[s]:
      standard_labels[f] = [major, std]

with open("standard_level.json", "w") as f:
   json.dump(standard_labels, f, indent=4)