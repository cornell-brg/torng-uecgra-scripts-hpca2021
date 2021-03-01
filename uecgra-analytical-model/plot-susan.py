#! /usr/bin/env python
#=========================================================================
# plot-susan.py
#=========================================================================
# Visualize a dataflow graph
#
# Author : Christopher Torng
# Date   : August 13, 2019
#

import os

from DfgJsonReader import DfgJsonReader

# Create a graph and plot it (i.e., dump a graphviz .dot file)

dfg = DfgJsonReader( 'jsons/susan_pro.json' )

g = dfg.get()
g.plot( dot_f='susan.dot' )

# Convert to PDF

os.system( 'dot -Tpdf susan.dot > susan.pdf' )


