#! /usr/bin/env python
#=========================================================================
# DfgJsonReader.py
#=========================================================================
# Imports a DFG from a CGRA configuration files (json).
#
# Author : Christopher Torng
# Date   : August 20, 2019
#

from Graph import Graph

class DfgJsonReader():

  def __init__( s, json ):
    s.json = json
    s.g    = Graph()
    s.g.configure_json( json )

  def get( s ):
    return s.g

  def plot( s ):
    s.g.plot( dot_f = s.json.split('/')[-1] + '.dot' )


