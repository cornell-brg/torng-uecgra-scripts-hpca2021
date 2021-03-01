#! /usr/bin/env python
#=========================================================================
# Graph.py
#=========================================================================
# Class for representing dataflow graphs composed of nodes with operators
# at specific voltages and frequencies.
#
# Author : Christopher Torng
# Date   : June 2, 2019
#

import json

from Node import Node
from parameters import conf_dvfs, conf_ops

class Graph( object ):

  def __init__( s ):
    s.nodes   = {}

    s.srcs_adjlist = {} # srcs_adjlist[x] gives all nodes that point to x
    s.dsts_adjlist = {} # dsts_adjlist[x] gives all nodes that x points to

    # Track recurrence (backwards) edges so we can remove them during the
    # topological sort

    s.recurrence_edges = []

    # JSON file for dumping

    s.json = 'graph.json'

  # Nodes

  def add_node( s, node ):
    key = node.name
    assert key not in s.nodes.keys(), \
      'Duplicate node %s! If this is intentional, first change the node name' % key
    s.nodes[ key ] = node

  def get_node( s, node_name ):
    return s.nodes[ node_name ]

  def delete_node( s, node_name ):
    del s.nodes[ node_name ]

  def all_nodes( s ):
    return s.nodes.keys()

  # Edges

  def get_srcs( s, node_name ):
    if node_name in s.srcs_adjlist.keys():
      return s.srcs_adjlist[ node_name ]
    else:
      return []

  def get_dsts( s, node_name ):
    if node_name in s.dsts_adjlist.keys():
      return s.dsts_adjlist[ node_name ]
    else:
      return []

  # Live-ins and Live-outs

  def get_liveins( s ):
    # Live-ins have no srcs
    return [ n for n in s.all_nodes() if n not in s.srcs_adjlist.keys() ]

  def get_liveouts( s ):
    # Live-outs have no dsts
    return [ n for n in s.all_nodes() if n not in s.dsts_adjlist.keys() ]

  #-----------------------------------------------------------------------
  # Connect
  #-----------------------------------------------------------------------

  # If this is a recurrence (backwards) edge, then mark it so we can
  # remove it during the topological sort

  def connect( s, src_name, dst_name, recurrence=False ):

    if src_name not in s.dsts_adjlist.keys():
      s.dsts_adjlist[ src_name ] = set()
    s.dsts_adjlist[ src_name ].add( dst_name )

    if dst_name not in s.srcs_adjlist.keys():
      s.srcs_adjlist[ dst_name ] = set()
    s.srcs_adjlist[ dst_name ].add( src_name )

    if recurrence:
      s.recurrence_edges.append( (src_name, dst_name) )

  def disconnect( s, src_name, dst_name, recurrence=False ):

    if src_name in s.dsts_adjlist.keys():
      if dst_name in s.dsts_adjlist[ src_name ]:
        s.dsts_adjlist[ src_name ].remove( dst_name )
      if len( s.dsts_adjlist[ src_name ] ) == 0:
        del( s.dsts_adjlist[ src_name ] )

    if dst_name in s.srcs_adjlist.keys():
      if src_name in s.srcs_adjlist[ dst_name ]:
        s.srcs_adjlist[ dst_name ].remove( src_name )
      if len( s.srcs_adjlist[ dst_name ] ) == 0:
        del( s.srcs_adjlist[ dst_name ] )

  #-----------------------------------------------------------------------
  # Ordering
  #-----------------------------------------------------------------------

  def topological_sort( s ):

    order = []

    # Make a deep copy of the edges (destructive algorithm)

    adjlist = {}
    for node_name, src_list in s.srcs_adjlist.items():
      adjlist[ node_name ] = list(src_list)

    # Remove any recurrence edges

    for e in s.recurrence_edges:
      src_name, dst_name = e
      idx = adjlist[ dst_name ].index( src_name )
      del( adjlist[ dst_name ][ idx ] )

    # Consider all nodes in the graph

    nodes = set( s.all_nodes() )

    # Topological sort

    while( nodes ):

      nodes_with_deps    = set( adjlist.keys() )
      nodes_without_deps = nodes.difference( nodes_with_deps )

      order.extend( nodes_without_deps )
      nodes = nodes_with_deps

      keys_to_delete = []
      for node_name, src_list in adjlist.items():
        idx_to_delete = []
        for i, src in enumerate( src_list ):
          if src in order:
            idx_to_delete.append( i )
        for i in reversed( idx_to_delete ):
          del( src_list[i] )
        if src_list == []:
          keys_to_delete.append( node_name )

      for k in keys_to_delete:
        del( adjlist[k] )

      # Breaking a cycle for topo sort
      #
      # - If we detect a cycle, break a random edge
      #

      if not nodes_without_deps:
        any_node = list(nodes)[0]
        print( 'Note: Randomly breaking edge -- from', \
                 adjlist[any_node][-1], 'to', any_node )
        del( adjlist[any_node][-1] )
        if adjlist[any_node] == []:
          del( adjlist[any_node] )

    return order

  #-----------------------------------------------------------------------
  # Import
  #-----------------------------------------------------------------------

  # dump_vf_json
  #
  # Take a config json and dump new VF into it

  def dump_vf_json( s, suffix='_dvfs' ):

    try:
      with open( s.json, 'r' ) as fd:
        data = json.load( fd )
    except FileNotFoundError:
      # If there is no json found (e.g., if this is a toy DFG constructed
      # by hand, then we do not dump anything...
      print( 'Warning: This DFG was not described as a json, so there is '
             'no json to dump the VF configuration into. Load a json '
             'file if you want to map to a real CGRA in hardware.' )
      return

    def get_name( xi, yi ):
      name_tmpl = 'x{}_y{}'
      return name_tmpl.format( xi, yi )

    # Dump new VF

    for config in data:
      xi = config['x']
      yi = config['y']
      name = get_name( xi, yi )
      node_name = [ _ for _ in s.all_nodes() if _.startswith( name ) ][0]
      node = s.get_node( node_name )
      if   node.V < 0.65 : config['dvfs'] = 'rest'
      elif node.V < 0.95 : config['dvfs'] = 'nominal'
      else               : config['dvfs'] = 'sprint'

    new_json = s.json.split('.json')[0] + suffix + '.json'
    with open( new_json, 'w' ) as fd:
        json.dump( data, fd, sort_keys=True, indent=4,
                       separators=(',', ': ') )

  # configure_json
  #
  # Import the graph from a JSON. The configuration JSON should have
  # config settings for each tile in the CGRA so we can reconstruct the
  # DFG.

  def configure_json( s, json_f ):

    s.json = json_f

    with open( json_f, 'r' ) as fd:
      data = json.load( fd )

    # Get x and y dimensions
    #
    # Just get the max dimension indices from the data and add one (assuming
    # the dimensions are zero-indexed)

    xdim = max( d['x'] for d in data ) + 1
    ydim = max( d['y'] for d in data ) + 1

    # Construct the graph and all the nodes
    #
    # All nodes will be named by their coordinate:
    #
    #     name_tmpl = 'x{}_y{}'
    #
    # This step makes one node for each entry in the json configuration
    #

    def get_name( xi, yi ):
      if xi <= -1:   return False
      if yi <= -1:   return False
      if xi >= xdim: return False
      if yi >= ydim: return False
      name_tmpl = 'x{}_y{}'
      return name_tmpl.format( xi, yi )

    # Gather data in a more accessible way

    data_name = {}
    for config in data:
      xi = config['x']
      yi = config['y']
      name = get_name( xi, yi )
      data_name[name] = dict( config )

    # Configure each node based on the json configuration data

    for config in data:
      op   = config['op']
      op   = op.lower().rstrip("'") # sanitize
      name = get_name( xi=config['x'], yi=config['y'] )
      s.add_node( Node( name=name, label=op, graph=s ) )

    # Configure each node based on the json configuration data

    for config in data:

      # Get the configuration
      #
      # Config JSON spec from our readme
      #
      # Available src  : "N", "S", "W", "E", "self"
      # Available dst  : "N", "S", "W", "E", "self", "none"
      # Available op   : "cp0", "cp1", "add", "sub", "sll", "srl", "and", "or'", "xor",
      #                    "eq'", "ne'", "gt'", "geq", "lt'", "leq", "mul", "phi", "nop", "br"
      # Available dvfs : "slow", "nominal", "fast"
      #
      # Note that the above options are all case insensitive
      # [
      #   {
      #     "x"           : 0,            // int: coordiate X
      #     "y"           : 5,            // int: coordiate Y
      #     "op"          : "none",       // string (op): "none", "add", etc
      #     "src_a"       : "self",       // string (src of opd a): "self", "N", "E", etc
      #     "src_b"       : "self",       // string (src of opd b): "self", "N", "E", etc
      #     "dst"         : [ "S", "E" ], // list of string (outports for compute)
      #     "bps_src"     : "N",          // string (bypass src), if this field is missing. then it will be set to "self"
      #     "bps_dst"     : [ "W" ],      // list of string (bypass dst), if this field is missing. then it will be set to [ "none" ]
      #     "bps_alt_src" : "E",          // string (alternative bypass src), if this field is missing. then it will be set to "self"
      #     "bps_alt_dst" : [ "N" ],      // list of string (alternative bypass dst), if this field is missing. then it will be set to [ "none" ]
      #     "dvfs"        : "nominal"
      #   },
      # ]
      #
      # Note that the items or subitems do not need to appear if they are not used. For example, in above example, "op", "src_a", and "src_b" can be eliminated.
      #
      # One exception is the JSON format for the 'br' node. Note that branch does not support broadcast for compute dst, therefore the compute dst is not a list.
      #
      # [
      #   {
      #     "x"           : 1,
      #     "y"           : 2,
      #     "op"          : "br",
      #     "src_data"    : "S",     // string (data): the "data" incoming port
      #     "src_bool"    : "E",     // string (bool): the "bool" outgoing port
      #     "dst_true"    : "N",     // string (dst true): the "data" outgoing port if "bool" is true
      #     "dst_false"   : "none",  // string (dst false): the "data" outgoing port if "bool" is false
      #     "bps_src"     : "N",     // string (bypass src), if this field is missing. then it will be set to "self"
      #     "bps_dst"     : [ "S" ], // list of string (bypass dst), if this field is missing. then it will be set to [ "none" ]
      #     "bps_alt_src" : "E",     // string (alternative bypass src), if this field is missing. then it will be set to "self"
      #     "bps_alt_dst" : [ "N" ], // list of string (alternative bypass dst), if this field is missing. then it will be set to [ "none" ]
      #     "dvfs"        : "nominal"
      #   },
      # ]
      #

      xi          = config['x']           if 'x'           in config.keys() else False
      yi          = config['y']           if 'y'           in config.keys() else False

      op          = config['op']          if 'op'          in config.keys() else False
      srca        = config['src_a']       if 'src_a'       in config.keys() else False
      srcb        = config['src_b']       if 'src_b'       in config.keys() else False
      dst         = config['dst']         if 'dst'         in config.keys() else False
      bps_src     = config['bps_src']     if 'bps_src'     in config.keys() else False
      bps_dst     = config['bps_dst']     if 'bps_dst'     in config.keys() else False
      bps_alt_src = config['bps_alt_src'] if 'bps_alt_src' in config.keys() else False
      bps_alt_dst = config['bps_alt_dst'] if 'bps_alt_dst' in config.keys() else False
      dvfs        = config['dvfs']        if 'dvfs'        in config.keys() else False

      src_data    = config['src_data']    if 'src_data'    in config.keys() else False
      src_bool    = config['src_bool']    if 'src_bool'    in config.keys() else False
      dst_true    = config['dst_true']    if 'dst_true'    in config.keys() else False
      dst_false   = config['dst_false']   if 'dst_false'   in config.keys() else False

      # Identify tile type

      is_br     = True if 'src_bool'     in config.keys() else False
      is_byp    = True if 'bps_src'      in config.keys() else False
      is_bypalt = True if 'bps_alt_src'  in config.keys() else False

      # Sanitize

      op = op.lower().rstrip("'") # sanitize

      # Grab the node that corresponds to this xy tile

      name = get_name( xi, yi )
      node = s.get_node( name )

      # Configure -- DVFS mode

      try:
        node.V = conf_dvfs[ dvfs ]['V']
        node.T = conf_dvfs[ dvfs ]['T']
      except KeyError:
        assert False, 'Error: Unsupported dvfs mode "%s"' % dvfs

      # Configure -- op

      try:
        node.op = conf_ops[ op ]
      except KeyError:
        assert False, 'Error: Unsupported op "%s"' % op

      # Configure -- Add edges for srcs and dsts
      #
      # The graph connect() method handles duplicate edges internally
      # (with a set). We can just loop over all nodes and connect
      # srcs/dsts even though this will connect the same nodes up to
      # twice.

      edges = set()

      def get_srcdst_name( xi, yi, srcdst, get_name ):
        if   srcdst == 'N'    : name = get_name( xi,   yi+1 )
        elif srcdst == 'E'    : name = get_name( xi+1, yi   )
        elif srcdst == 'S'    : name = get_name( xi,   yi-1 )
        elif srcdst == 'W'    : name = get_name( xi-1, yi   )
        elif srcdst == 'self' : name = get_name( xi,   yi   )
        else: assert False, 'Error: Unsupported srcdst identifier "%s"' % srcdst
        return name

      # Normal non-branch tiles

      if not is_br:

        if srca == 'self' and srcb == 'self' and 'none' in dst:
          continue # detect empty nodes only used for bypass

        from_srca_name = get_srcdst_name( xi, yi, srca, get_name )
        if not from_srca_name: # sanitize from sram
          name_sram = name+'_ld_sram'
          s.add_node( Node( name=name_sram, op='sram', label='sram', graph=s ) )
          s.connect( name_sram, name )
        else:
          if from_srca_name == name:
#            s.connect( from_srca_name, name, recurrence=True )
            pass # ignore self edges...
          else:
            s.connect( from_srca_name, name )

        from_srcb_name = get_srcdst_name( xi, yi, srcb, get_name )
        if not from_srcb_name: # sanitize from sram
          name_sram = name+'_ld_sram'
          s.add_node( Node( name=name_sram, op='sram', label='sram', graph=s ) )
          s.connect( name_sram, name )
        else:
          if from_srcb_name == name:
#            s.connect( from_srcb_name, name, recurrence=True )
            pass # ignore self edges...
          else:
            s.connect( from_srcb_name, name )

        for d in dst:
          if d == 'none': continue # sanitize
          to_dst_name = get_srcdst_name( xi, yi, d, get_name )
          if not to_dst_name: # sanitize to sram
            name_sram = name+'_st_sram'
            s.add_node( Node( name=name_sram, op='sram', label='sram', graph=s ) )
            s.connect( name, name_sram )
          else:
            if to_dst_name == name:
#              s.connect( name, to_dst_name, recurrence=True )
              pass # ignore self edges...
            else:
              s.connect( name, to_dst_name )

      # Branch tiles

      else:
        from_srca_name = get_srcdst_name( xi, yi, src_data, get_name )
        from_srcb_name = get_srcdst_name( xi, yi, src_bool, get_name )

        if not from_srca_name: # sanitize from sram
          assert False, "Branches probably shouldn't also be loads"
        else:
          if from_srca_name == name:
#            s.connect( from_srca_name, name, recurrence=True )
            pass # ignore self edges...
          else:
            s.connect( from_srca_name, name )
        if not from_srcb_name: # sanitize from sram
          assert False, "Branches probably shouldn't also be loads"
        else:
          if from_srcb_name == name:
#            s.connect( from_srcb_name, name, recurrence=True )
            pass # ignore self edges...
          else:
            s.connect( from_srcb_name, name )

        for d in [ dst_true, dst_false ]:
          if d == 'none': continue # sanitize
          to_dst_name = get_srcdst_name( xi, yi, d, get_name )
          if not to_dst_name: # sanitize to sram
            assert False, "Branches probably shouldn't also be stores"
          else:
            if to_dst_name == name:
              pass # ignore dsts to self for branches
            else:
              s.connect( name, to_dst_name )

          # FIXME: br and phi node simulator behavior
          # FIXME: how to tell which are recurrence edges

    # Bypass paths
    #
    # We create entirely new nodes for bypass paths to decouple their
    # firing logic from the main op paths. To do this, we wait for the
    # original DFG to be built. Then we make a pass over all nodes and for
    # each bypass, we extract it as a new node.

    for config in data:

      xi          = config['x']           if 'x'           in config.keys() else False
      yi          = config['y']           if 'y'           in config.keys() else False
      bps_src     = config['bps_src']     if 'bps_src'     in config.keys() else False
      bps_dst     = config['bps_dst']     if 'bps_dst'     in config.keys() else False
      bps_alt_src = config['bps_alt_src'] if 'bps_alt_src' in config.keys() else False
      bps_alt_dst = config['bps_alt_dst'] if 'bps_alt_dst' in config.keys() else False

      name = get_name( xi, yi )

      is_byp    = True if 'bps_src'      in config.keys() else False
      is_bypalt = True if 'bps_alt_src'  in config.keys() else False

      if is_byp:
        name_byp = name+'_byp'
        s.add_node( Node( name=name_byp, op='byp', label='byp', graph=s ) )

      if is_bypalt:
        name_bypalt = name+'_bypalt'
        s.add_node( Node( name=name_bypalt, op='byp', label='bypalt', graph=s ) )

    for config in data:

      xi          = config['x']           if 'x'           in config.keys() else False
      yi          = config['y']           if 'y'           in config.keys() else False

      op          = config['op']          if 'op'          in config.keys() else False
      srca        = config['src_a']       if 'src_a'       in config.keys() else False
      srcb        = config['src_b']       if 'src_b'       in config.keys() else False
      dst         = config['dst']         if 'dst'         in config.keys() else False
      bps_src     = config['bps_src']     if 'bps_src'     in config.keys() else False
      bps_dst     = config['bps_dst']     if 'bps_dst'     in config.keys() else False
      bps_alt_src = config['bps_alt_src'] if 'bps_alt_src' in config.keys() else False
      bps_alt_dst = config['bps_alt_dst'] if 'bps_alt_dst' in config.keys() else False
      dvfs        = config['dvfs']        if 'dvfs'        in config.keys() else False

      src_data    = config['src_data']    if 'src_data'    in config.keys() else False
      src_bool    = config['src_bool']    if 'src_bool'    in config.keys() else False
      dst_true    = config['dst_true']    if 'dst_true'    in config.keys() else False
      dst_false   = config['dst_false']   if 'dst_false'   in config.keys() else False

      name        = get_name( xi, yi )
      name_byp    = get_name( xi, yi ) + '_byp'
      name_bypalt = get_name( xi, yi ) + '_bypalt'

      is_byp    = True if 'bps_src'      in config.keys() else False
      is_bypalt = True if 'bps_alt_src'  in config.keys() else False

      def reverse_direction( d ):
        if d == 'N': return 'S'
        if d == 'E': return 'W'
        if d == 'S': return 'N'
        if d == 'W': return 'E'
        assert False

      if is_byp:
        from_src_name = get_srcdst_name( xi, yi, bps_src, get_name )
        if not from_src_name: # sanitize from sram
          name_sram = name+'_byp_ld_sram'
          s.add_node( Node( name=name_sram, op='sram', label='sram', graph=s ) )
          s.connect( name_sram, name_byp )
        else:
          # disconnect if no srcs use this edge
          if bps_src != srca and \
             bps_src != srcb and \
             bps_src != src_data and \
             bps_src != src_bool:
            s.disconnect( from_src_name, name )
          # reconnect
          src_data = data_name[from_src_name]
          if   'dst' in src_data.keys() and reverse_direction( bps_src ) in src_data['dst']:
            s.connect( from_src_name, name_byp )
          elif 'dst_true' in src_data.keys() and reverse_direction( bps_src ) in src_data['dst_true']:
            s.connect( from_src_name, name_byp )
          elif 'dst_false' in src_data.keys() and reverse_direction( bps_src ) in src_data['dst_false']:
            s.connect( from_src_name, name_byp )
          elif 'bps_dst' in src_data.keys() and reverse_direction( bps_src ) in src_data['bps_dst']:
            s.connect( from_src_name+'_byp', name_byp )
          elif 'bps_alt_dst' in src_data.keys() and reverse_direction( bps_src ) in src_data['bps_alt_dst']:
            s.connect( from_src_name+'_bypalt', name_byp )

        for d in bps_dst:
          to_dst_name = get_srcdst_name( xi, yi, d, get_name )
          if not to_dst_name: # sanitize to sram
            name_sram = name+'_byp_st_sram'
            s.add_node( Node( name=name_sram, op='sram', label='sram', graph=s ) )
            s.connect( name_byp, name_sram )
          else:
            # disconnect if no dsts use this edge
            if (not dst or d not in dst) and \
               not d == dst_true and \
               not d == dst_false:
              s.disconnect( name, to_dst_name )
            # reconnect
            dst_data = data_name[to_dst_name]
            if   'src_a' in dst_data.keys() and reverse_direction( d ) == dst_data['src_a']:
              s.connect( name_byp, to_dst_name )
            elif 'src_b' in dst_data.keys() and reverse_direction( d ) == dst_data['src_b']:
              s.connect( name_byp, to_dst_name )
            elif 'src_data' in dst_data.keys() and reverse_direction( d ) == dst_data['src_data']:
              s.connect( name_byp, to_dst_name )
            elif 'src_bool' in dst_data.keys() and reverse_direction( d ) == dst_data['src_bool']:
              s.connect( name_byp, to_dst_name )
            elif 'bps_src' in dst_data.keys() and reverse_direction( d ) == dst_data['bps_src']:
              s.connect( name_byp, to_dst_name+'_byp' )
            elif 'bps_alt_src' in dst_data.keys() and reverse_direction( d ) == dst_data['bps_alt_src']:
              s.connect( name_byp, to_dst_name+'_bypalt' )

      if is_bypalt:
        from_src_name = get_srcdst_name( xi, yi, bps_alt_src, get_name )
        if not from_src_name: # sanitize from sram
          name_sram = name+'_bypalt_ld_sram'
          s.add_node( Node( name=name_sram, op='sram', label='sram', graph=s ) )
          s.connect( name_sram, name_bypalt )
        else:
          # disconnect if no srcs use this edge
          if bps_alt_src != srca and \
             bps_alt_src != srcb and \
             bps_alt_src != src_data and \
             bps_alt_src != src_bool:
            s.disconnect( from_src_name, name )
          # reconnect
          src_data = data_name[from_src_name]
          if   'dst' in src_data.keys() and reverse_direction( bps_alt_src ) in src_data['dst']:
            s.connect( from_src_name, name_bypalt )
          elif 'dst_true' in src_data.keys() and reverse_direction( bps_alt_src ) in src_data['dst_true']:
            s.connect( from_src_name, name_bypalt )
          elif 'dst_false' in src_data.keys() and reverse_direction( bps_alt_src ) in src_data['dst_false']:
            s.connect( from_src_name, name_bypalt )
          elif 'bps_dst' in src_data.keys() and reverse_direction( bps_alt_src ) in src_data['bps_dst']:
            s.connect( from_src_name+'_byp', name_bypalt )
          elif 'bps_alt_dst' in src_data.keys() and reverse_direction( bps_alt_src ) in src_data['bps_alt_dst']:
            s.connect( from_src_name+'_bypalt', name_bypalt )

        for d in bps_alt_dst:
          to_dst_name = get_srcdst_name( xi, yi, d, get_name )
          if not to_dst_name: # sanitize to sram
            name_sram = name+'_bypalt_st_sram'
            s.add_node( Node( name=name_sram, op='sram', label='sram', graph=s ) )
            s.connect( name_bypalt, name_sram )
          else:
            # disconnect if no dsts use this edge
            if (not dst or d not in dst) and \
               not d == dst_true and \
               not d == dst_false:
              s.disconnect( name, to_dst_name )
            # reconnect
            dst_data = data_name[to_dst_name]
            if   'src_a' in dst_data.keys() and reverse_direction( d ) == dst_data['src_a']:
              s.connect( name_bypalt, to_dst_name )
            elif 'src_b' in dst_data.keys() and reverse_direction( d ) == dst_data['src_b']:
              s.connect( name_bypalt, to_dst_name )
            elif 'src_data' in dst_data.keys() and reverse_direction( d ) == dst_data['src_data']:
              s.connect( name_bypalt, to_dst_name )
            elif 'src_bool' in dst_data.keys() and reverse_direction( d ) == dst_data['src_bool']:
              s.connect( name_bypalt, to_dst_name )
            elif 'bps_src' in dst_data.keys() and reverse_direction( d ) == dst_data['bps_src']:
              s.connect( name_bypalt, to_dst_name+'_byp' )
            elif 'bps_alt_src' in dst_data.keys() and reverse_direction( d ) == dst_data['bps_alt_src']:
              s.connect( name_bypalt, to_dst_name+'_bypalt' )

    # Remove orphan nodes

    to_delete = []

    for node_name in s.all_nodes():
      srcs = s.get_srcs( node_name )
      dsts = s.get_dsts( node_name )
      if not srcs and not dsts:
        to_delete.append( node_name )

    for _ in to_delete:
      s.delete_node( _ )

  #-----------------------------------------------------------------------
  # Drawing
  #-----------------------------------------------------------------------

  # plot
  #
  # Dumps a graphviz dot file

  def plot( s, dot_title='', dot_f='graph.dot' ):

    # Templates for generating graphviz dot statements

    graph_template = \
'''\
digraph {{
label="{title}";
labelloc="t";
fontsize=60;
size="8.5;11";
ratio="fill";
margin=0;
pad=1;
rankdir="TB";
concentrate=true;
splines=polyline;
center=true;
nodesep=1.2;
ranksep=0.8;
{nodes}
{edges}
}}\
'''

    node_template = \
      '{dot_id} [ fontsize=24, width=2, penwidth=2, label="{name}\n{label}", color=black ];'

    edge_template = \
      '{src_dot_id}:s -> {dst_dot_id}:n [ arrowsize=2, penwidth=2 ];'

    # Loop over all nodes and generate a graphviz node declaration

    dot_nodes = []

    for node_name in s.all_nodes():
      node_cfg           = {}
      node_cfg['dot_id'] = node_name
      node_cfg['name']   = node_name
      node_cfg['label']  = s.get_node( node_name ).label

      dot_nodes.append( node_template.format( **node_cfg ) )

    # Loop over all edges and generate graphviz edge commands

    dot_edges = []

    for dst in s.srcs_adjlist.keys():
      for src in s.srcs_adjlist[ dst ]:
        e_cfg = {}
        e_cfg['src_dot_id']  = src
        e_cfg['dst_dot_id']  = dst

        dot_edges.append( edge_template.format( **e_cfg ) )

    # Write out the graphviz dot graph file

    with open( dot_f, 'w' ) as fd:
      graph_cfg = {}
      graph_cfg['title'] = dot_title
      graph_cfg['nodes'] = '\n'.join( dot_nodes )
      graph_cfg['edges'] = '\n'.join( dot_edges )
      fd.write( graph_template.format( **graph_cfg ) )

