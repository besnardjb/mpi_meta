import os
import json

bindings = {}

with open("./standard_level.json","r") as f:
   bindings = json.load(f)

stds = ["1.0","1.1","1.3","2.0","2.1","2.2","3.0", "3.1", "4.0"]

print("""
<html>

<head>
<style>
html,
body {
	height: 100%;
}

h1 {
   text-align: center;
   text-shadow: -1px -1px #0c0, 1px 1px #060, -3px 0 4px #000;
   color: #FFF;
}

body {
	margin: 0;
	background: #000;
	font-family: sans-serif;
	font-weight: 100;
   text-allign: center;
}

[data-tooltip]::before {
    position : absolute;
    content : attr(data-tooltip);
    background: #000;
    opacity : 0;
}

[data-tooltip]:hover::before {
    opacity : 1;
}

[data-tooltip]:not([data-tooltip-persistent])::before {
    pointer-events: none;
}

table {
   margin-left:10%;
   margin-right:10%;
	width: 80%;
	border-collapse: collapse;
	overflow: hidden;
	box-shadow: 0 0 20px rgba(0,0,0,0.1);
}

th,
td {
	padding: 15px;
	background-color: rgba(255,255,255,0.2);
	color: #fff;
}

th {
	text-align: left;
}

thead {
	th {
		background-color: #55608f;
	}
}



tbody > tr:hover {background-color: rgba(100,100,100);}


#deprecated {
   color: orange;
}

#present {
   color: lightgreen;
}

#notpresent {
   color: red;
}

</style>


<title>Table of MPI Functions</title>
</head>

<body>

<h1>MPI Function Table</h1>

<div class="container">
<table>
  <thead>
    <th>MPI Functions</th>
""")

for s in stds:
   print("    <th>{}</th>".format(s))

print("""
</thead>
<tbody>""")

funcs = [x for x in bindings.keys()]
funcs.sort()

def has_dep(f):
   dep = [x for x in bindings[f] if x.startswith("DEPBY")]
   if len(dep):
      return float(dep[0].split(":")[1])
   return None

def get_symbol_for_std(f, std):
   std_int_val = float(std)

   if "STD:{}".format(std) not in bindings[f]:
      return "<div data-tooltip='{}' id='notpresent'>&#10006;</div>".format(std)

   deprecated_txt = "<div data-tooltip='{}' id='deprecated'>&#9888;</div>".format(std)
   dep = has_dep(f)
   if dep:
      if dep < std_int_val:
         return deprecated_txt
   if "DEPBY:{}".format(std) in bindings[f]:
      return deprecated_txt

   return "<div data-tooltip='{}' id='present'>&#10004;</div>".format(std)



for f in funcs:
   print("""
<tr>
    <td><b>{}</b></td>
""".format(f))
   for s in stds:
      print("    <td>{}</td>".format(get_symbol_for_std(f, s)))







print("""
</tbody>
</table>
</div>
</body>
""")