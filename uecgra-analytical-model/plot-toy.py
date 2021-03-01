#! /usr/bin/env python
#=========================================================================
# plot-bf.py
#=========================================================================
# Visualize a dataflow graph
#
# Author : Christopher Torng
# Date   : August 13, 2019
#

import os

from dfgs import ToyDfg4 as toydfg

# Create a graph and plot it (i.e., dump a graphviz .dot file)

g = toydfg().get()
g.plot( dot_f='toy.dot' )

# Convert to PDF

os.system( 'dot -Tpdf toy.dot > toy.pdf' )


