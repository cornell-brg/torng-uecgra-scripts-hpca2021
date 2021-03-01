#! /usr/bin/env python
#=========================================================================
# Node.py
#=========================================================================
# Class for representing nodes in the dataflow graph. A node has an
# operator and runs at a specific voltage and frequency.
#
# Author : Christopher Torng
# Date   : August 13, 2019
#

class Node( object ):

  def __init__( s, name, graph, op='mul', label='',
                                V_N=0.9,  T_N=1.0 ):

    s.name  = name
    s.g     = graph

    s.op    = op
    s.label = label

    s.V     = V_N
    s.T     = T_N

  def set_op( s, op ):
    s.op = op

  def set_V( s, V ):
    s.V = V

  def set_T( s, T ):
    s.T = T

  def all_srcs( s ):
    return s.g.get_srcs( s.name )

  def all_dsts( s ):
    return s.g.get_dsts( s.name )


