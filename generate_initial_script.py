#!/usr/bin/env python3

import sys, re, os

d2v_pattern = re.compile(r"\[\[d2v\]\]")
trim_pattern = re.compile("\[\[trims:(\d+)\]\]")

def add_trims(line):
    trims = []
    m = trim_pattern.search(line)
    for _ in range(int(m.group(1))):
        trims.append("Trim(0,0)")
    return "++".join(trims)


if len(sys.argv) < 4:
    print("Usage: {0} template d2v epnum".format(sys.argv[0]))
    sys.exit(1)

template = sys.argv[1]
d2v = sys.argv[2]
avs = "{0}.avs".format(sys.argv[3])

temp_lines = []
try:
    with open(template) as f:
        temp_lines = f.read().splitlines()
except IOError:
    print("Supplied template does not exist.")
    sys.exit(1)


print(temp_lines)

with open(avs, "w") as out:
    for line in temp_lines:
        if d2v_pattern.search(line):
            line = d2v_pattern.sub(d2v, line)
        if trim_pattern.search(line):
            line = add_trims(line)
        out.write("{0}{1}".format(line,os.linesep))
