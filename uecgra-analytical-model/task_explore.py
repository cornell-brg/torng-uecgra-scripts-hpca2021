#! /usr/bin/env python
#=========================================================================
# task_explore.py
#=========================================================================
# A doit task script that generates a subtask for every possible
# voltage-frequency configuration in a given DFG.
#
# Author : Christopher Torng
# Date   : August 15, 2019
#

from PowerModel import PowerModel
from dfgs       import ToyDfg4 as DFG

import json
import os
import numpy as np

def merge_json( keys, json_files, dumpfile ):
  data = {}
  for k, output in zip( keys, json_files ):
    if not os.path.exists( output ): continue
    data[k] = json.load( open(output, 'r') )
  with open( dumpfile, 'w' ) as fd:
    json.dump( data, fd, sort_keys=True, indent=4, separators=(',', ': ') )

def merge_json_list( keys, json_files, dumpfile ):
  data = { 'ee' : [], 'label' : [], 'perf' : [] }
  for k, output in zip( keys, json_files ):
    if not os.path.exists( output ): continue
    x = json.load( open(output, 'r') )
    data['ee'].append( x['ee'] )
    data['label'].append( x['label'] )
    data['perf'].append( x['perf'] )
  with open( dumpfile, 'w' ) as fd:
    json.dump( data, fd, sort_keys=True, indent=4, separators=(',', ': ') )

def dump_data( dumpfile, label, PERF_N, E_N, V1, V2, V3, V4, V5, V6 ):

  model = PowerModel( graph = DFG().get() )
  V_range = {
      'i_sram1' : V1,
            '0' : V2,
            '1' : V3,
            '2' : V4,
            '3' : V5,
            '4' : V5,
            '5' : V5,
            '6' : V5,
            '7' : V5,
            '8' : V5,
            '9' : V5,
      'o_sram1' : V6,
  }
  op_range = {
      'i_sram1' : 'sram',
            '0' : 'alu',
            '1' : 'mul',
            '2' : 'alu',
            '3' : 'alu',
            '4' : 'alu',
            '5' : 'alu',
            '6' : 'alu',
            '7' : 'alu',
            '8' : 'alu',
            '9' : 'alu',
      'o_sram1' : 'sram',
  }
  model.set_V_range( V_range )
  model.set_op_range( op_range )

  model.calc_performance()
  data = {}
  data['label'] = label
  data['perf']  = PERF_N / model.latency
  data['ee']    = E_N / model.E_cgra_total()
  with open( dumpfile, 'w' ) as fd:
    json.dump( data, fd, sort_keys=True, indent=4,
      separators=(',', ': ') )

def task_explore():

  base = { \
    'basename' : 'explore',
    'uptodate' : [ True ], # Don't rebuild if targets exists
  }

#  Vs = np.arange(0.63,1.43,0.20)
  Vs = [ 0.61, 0.90, 1.23 ]
#  Vs = [ 0.90, 1.23 ]
#  Vs = [ 0.90 ]

  # Nominal throughput and energy

  model_N = PowerModel( graph = DFG().get() )
  model_N.calc_performance()
  PERF_N = model_N.latency
  E_N    = model_N.E_cgra_total()

  # Generate

  labels  = []
  targets = []

  for V1 in Vs:
    for V2 in Vs:
      for V3 in Vs:
        for V4 in Vs:
          for V5 in Vs:
            for V6 in Vs:
              label = "{:3.2f}_{:3.2f}_{:3.2f}_" \
                      "{:3.2f}_{:3.2f}_{:3.2f}".format( \
                         V1, V2, V3, V4, V5, V6 )

              dumpfile = 'explore-data/explore-' + label + '.json'

              taskdict = dict( base )
              taskdict.update( {
                'name'     : label,
                'actions'  : [ (dump_data, [dumpfile, label,
                  PERF_N, E_N, V1, V2, V3, V4, V5, V6 ]) ],
                'targets'  : [dumpfile],
                #'clean'    : [ 'rm -f ' + dumpfile ],
              } )

              labels  += [label]
              targets += [dumpfile]

              yield taskdict

  # Merge

  dumpfile = 'explore-data/plot-explore.json'

  taskdict = dict( base )
  taskdict.update( {
    'name'     : 'merge',
    'actions'  : [ (merge_json, [labels, targets, dumpfile]) ],
    'uptodate' : [ False ],
#    'targets'  : [dumpfile],
#    'file_dep' : targets
  } )

  yield taskdict

  # Merge

  dumpfile = 'explore-data/plot-explore-list.json'

  taskdict = dict( base )
  taskdict.update( {
    'name'     : 'merge-list',
    'actions'  : [ (merge_json_list, [labels, targets, dumpfile]) ],
    'uptodate' : [ False ],
#    'targets'  : [dumpfile],
#    'file_dep' : targets
  } )

  yield taskdict

