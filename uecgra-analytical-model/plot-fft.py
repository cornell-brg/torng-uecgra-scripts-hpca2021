#! /usr/bin/env python
#=========================================================================
# plot-fft.py
#=========================================================================
# Visualize a dataflow graph
#
# Author : Christopher Torng
# Date   : August 13, 2019
#

import os

from DfgJsonReader import DfgJsonReader

# Create a graph and plot it (i.e., dump a graphviz .dot file)

dfg = DfgJsonReader( 'jsons/fft_pro.json' )

g = dfg.get()
g.plot( dot_f='fft.dot' )

# Convert to PDF

os.system( 'dot -Tpdf fft.dot > fft.pdf' )


