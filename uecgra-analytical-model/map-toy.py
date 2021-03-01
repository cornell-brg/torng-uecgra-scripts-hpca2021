#! /usr/bin/env python
#=========================================================================
# map-toy.py
#=========================================================================
# Script to experiment with toy DFGs
#
# Author : Christopher Torng
# Date   : August 13, 2019
#

from Simulator     import Simulator
from PowerModel    import PowerModel

from dfgs import ToyDfg4 as toydfg

#-------------------------------------------------------------------------
# Graph
#-------------------------------------------------------------------------
# Create a graph and plot it (i.e., dump a graphviz .dot file)

g = toydfg().get()
g.plot()

#-------------------------------------------------------------------------
# Simulate and measure throughput
#-------------------------------------------------------------------------

sim = Simulator( graph = g, verbose=False, do_plot=False )

#-------------------------------------------------------------------------
# Measure power + Apply power-mapping pass
#-------------------------------------------------------------------------

p = PowerModel( graph = g, sim = sim, verbose=True )
p.autosearch()

