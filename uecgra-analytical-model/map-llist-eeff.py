#! /usr/bin/env python
#=========================================================================
# map-llist-eeff.py
#=========================================================================
# Map with energy-optimized mapping (eeff is for 'energy efficient')
#
# Author : Christopher Torng
# Date   : August 13, 2019
#

from DfgJsonReader import DfgJsonReader
from Simulator     import Simulator
from PowerModel    import PowerModel

#-------------------------------------------------------------------------
# Graph
#-------------------------------------------------------------------------
# Create a graph and plot it (i.e., dump a graphviz .dot file)

dfg = DfgJsonReader( 'jsons/llist.json' )

g = dfg.get()
g.plot()

#-------------------------------------------------------------------------
# Simulate and measure throughput
#-------------------------------------------------------------------------

sim = Simulator( graph = g, verbose=False, do_plot=False )

#-------------------------------------------------------------------------
# Measure power + Apply power-mapping pass
#-------------------------------------------------------------------------

p = PowerModel( graph = g, sim = sim, verbose=True )
p.autosearch( prioritize_energy = True )

