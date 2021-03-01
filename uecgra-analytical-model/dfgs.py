#! /usr/bin/env python
#=========================================================================
# dfgs.py
#=========================================================================
# Various toy DFGs (manually constructed) that can be experimented with
#
# Author : Christopher Torng
# Date   : August 20, 2019
#

from Graph import Graph
from Node  import Node

#-------------------------------------------------------------------------
# ToyDfg1
#-------------------------------------------------------------------------
# A toy series-parallel DFG with no recurrences
#

class ToyDfg1:

  def __init__( s ):

    s.g = Graph()

    s.g.add_node( Node( name='0', graph=s.g ) )
    s.g.add_node( Node( name='1', graph=s.g ) )
    s.g.add_node( Node( name='2', graph=s.g ) )
    s.g.add_node( Node( name='3', graph=s.g ) )
    s.g.add_node( Node( name='4', graph=s.g ) )
    s.g.add_node( Node( name='5', graph=s.g ) )
    s.g.add_node( Node( name='N', graph=s.g ) )

    s.g.connect( '0', '1' )
    s.g.connect( '0', '3' )
    s.g.connect( '1', '2' )
    s.g.connect( '2', 'N' )
    s.g.connect( '3', '4' )
    s.g.connect( '4', '5' )
    s.g.connect( '5', 'N' )

    s.g.add_node( Node( name='i_sram1', graph=s.g ) )
    s.g.connect( 'i_sram1', '0' )

    s.g.add_node( Node( name='o_sram1', graph=s.g ) )
    s.g.connect( 'N', 'o_sram1' )

  def get( s ):
    return s.g

  def plot( s ):
    s.g.plot( dot_f='graph.dot' )

#-------------------------------------------------------------------------
# ToyDfg2
#-------------------------------------------------------------------------
# A toy series-parallel DFG with no recurrences, with ops assigned

class ToyDfg2:

  def __init__( s ):

    s.g = Graph()

    s.g.add_node( Node( name='0', graph=s.g, op='byp' ) )
    s.g.add_node( Node( name='1', graph=s.g, op='mul' ) )
    s.g.add_node( Node( name='2', graph=s.g, op='byp' ) )
    s.g.add_node( Node( name='3', graph=s.g, op='byp' ) )
    s.g.add_node( Node( name='4', graph=s.g, op='byp' ) )
    s.g.add_node( Node( name='5', graph=s.g, op='byp' ) )
    s.g.add_node( Node( name='N', graph=s.g, op='byp' ) )

    s.g.connect( '0', '1' )
    s.g.connect( '0', '3' )
    s.g.connect( '1', '2' )
    s.g.connect( '2', 'N' )
    s.g.connect( '3', '4' )
    s.g.connect( '4', '5' )
    s.g.connect( '5', 'N' )

    s.g.add_node( Node( name='i_sram1', graph=s.g, op='zero' ) )
    s.g.connect( 'i_sram1', '0' )

    s.g.add_node( Node( name='o_sram1', graph=s.g, op='zero' ) )
    s.g.connect( 'N', 'o_sram1' )

  def get( s ):
    return s.g

  def plot( s ):
    s.g.plot( dot_f='graph.dot' )

#-------------------------------------------------------------------------
# ToyDfg3
#-------------------------------------------------------------------------
# A toy DFG with a recurrence

class ToyDfg3:

  def __init__( s ):

    s.g = Graph()

    for i in range( 7 ):
      s.g.add_node( Node( name=str(i), graph=s.g ) )

    s.g.connect( '0', '1' )
    s.g.connect( '0', '2' )
    s.g.connect( '1', '4' )
    s.g.connect( '2', '3' )
    s.g.connect( '3', '4' )
    s.g.connect( '4', '5' )
    s.g.connect( '5', '6' )
    s.g.connect( '6', '0', recurrence=True )

    s.g.add_node( Node( name='i_sram1', graph=s.g ) )
    s.g.connect( 'i_sram1', '0' )

    s.g.add_node( Node( name='o_sram1', graph=s.g ) )
    s.g.connect( '6', 'o_sram1' )

  def get( s ):
    return s.g

  def plot( s ):
    s.g.plot( dot_f='graph.dot' )

#-------------------------------------------------------------------------
# ToyDfg4
#-------------------------------------------------------------------------
# A toy DFG with a recurrence of a few nodes, in addition to many other
# nodes

class ToyDfg4:

  def __init__( s ):

    s.g = Graph()

    for i in range( 10 ):
      s.g.add_node( Node( name=str(i), graph=s.g ) )

    s.g.connect( '0', '1' )
    s.g.connect( '1', '2' )
    s.g.connect( '2', '3' )
    s.g.connect( '3', '0', recurrence=True )
    s.g.connect( '3', '4' )
    s.g.connect( '4', '5' )
    s.g.connect( '5', '6' )
    s.g.connect( '6', '7' )
    s.g.connect( '7', '8' )
    s.g.connect( '8', '9' )

    s.g.add_node( Node( name='i_sram1', graph=s.g ) )
    s.g.connect( 'i_sram1', '0' )

    s.g.add_node( Node( name='o_sram1', graph=s.g ) )
    s.g.connect( '9', 'o_sram1' )

  def get( s ):
    return s.g

  def plot( s ):
    s.g.plot( dot_f='graph.dot' )


