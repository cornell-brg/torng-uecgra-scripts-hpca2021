#! /usr/bin/env python
#=========================================================================
# parameters.py
#=========================================================================
# We consolidate shared analytical model parameters here
#
# Author : Christopher Torng
# Date   : August 22, 2019
#

# For each DVFS mode, specify a voltage and cycle time pair
#
# These numbers started from the SPICE-level voltage-frequency
# relationship in this process and were then tweaked to be rationally
# related (e.g., divide-by-2, divide-by-3). All tweaks are in the
# conservative direction (e.g., the rest mode should have a ~2.85 cycle
# time, normalized to the nominal cycle time, but we slow it down to 3.00
# to achieve a rational clocking relationship).
#

conf_dvfs = {
  'nominal' : { 'V': 0.90, 'T': 1.00 },
  'fast'    : { 'V': 1.23, 'T': 0.66 },
  'slow'    : { 'V': 0.61, 'T': 3.00 },
}

# Map intended configured operation to the subset of operations known in
# the analytical model..
#
#     key: (intended configured op), value: (closest analytical model op)
#
# The analytical model uses the op primarily for calculating power, which
# then impacts the choice of DVFS mode for each node in the DFG (which
# then impacts performance).

conf_ops = {
"cp0" : 'cp',
"cp1" : 'cp',
"add" : 'alu',
"sub" : 'alu',
"sll" : 'alu',
"srl" : 'alu',
"and" : 'alu',
"or" : 'alu',
"xor" : 'alu',
"eq" : 'cmp',
"ne" : 'cmp',
"gt" : 'cmp',
"geq" : 'cmp',
"lt" : 'cmp',
"leq" : 'cmp',
"mul" : 'mul',
"phi" : 'phi',
"nop" : 'zero',
"br"  : 'br',
}

