#! /usr/bin/env python
#=========================================================================
# PowerModel.py
#=========================================================================
# An analytical power model built with first-order equations. This also
# includes the compiler power-mapping algorithm -- see autosearch().
#
# This model corresponds to Section II.B and Section III in the paper.
#
# Author : Christopher Torng
# Date   : August 14, 2019
#

from functools import reduce

from Simulator import Simulator
from parameters import conf_dvfs

import json

#-------------------------------------------------------------------------
# Calculate power
#-------------------------------------------------------------------------

class PowerModel:

  def __init__( s, graph, sim=None, verbose=False ):

    s.verbose = verbose

    s.g = graph

    s.nodes = [ s.g.get_node( _ ) for _ in s.g.topological_sort() ]

    # Cycle-level throughput simulator

    s.sim = sim

    if not sim:
      s.sim = Simulator( graph = s.g )

    # Live-in and live-out nodes
    #
    # Track these nodes so we can use their voltages for the SRAMs
    # attached to them.

    s.l_node_names = s.g.get_liveins() + s.g.get_liveouts()
    s.l_nodes      = [ s.g.get_node( _ ) for _ in s.l_node_names ]

    # Hack to prevent constants from being modeled as srams/tiles

    s.nodes   = [ n for n in s.nodes   if n.op != 'const' ]
    s.l_nodes = [ n for n in s.l_nodes if n.op != 'const' ]

    # Number of nodes

    s.N_N = len( s.nodes )

    # Number of live-ins and live-outs
    #
    # Each tile that produces a live-in is assumed to have an SRAM behind
    # it, and each tile that consumes a live-out is assumed to have an
    # SRAM it feeds.

    s.N_L = len( s.l_node_names )

    # CGRA parameters

    s.N_T     = 64             # Number of tiles in 4 x 4 cgra
    s.N_T_on  = s.N_N          # Number of tiles being used
    s.N_T_off = s.N_T - s.N_N  # Number of tiles that are power-gated

    s.N_S     = 16             # Number of srams in 4 x 4 cgra
    s.N_S_on  = s.N_L          # Number of srams being used
    s.N_S_off = s.N_S - s.N_L  # Number of srams that are power-gated

    # Voltages

    s.V_N   = 0.9
    s.V_min = 0.65  # min voltage
    s.V_max = 1.25  # max voltage

    # alpha_*
    #
    # alpha_foo is the ratio of dynamic power of an operation foo to the
    # dynamic power of a tile executing a multiply.
    #
    # Latest GL results at 750MHz
    #
    #     5.5 / 5.5 = 1
    #     1.8 / 5.5 = 0.3273  # add
    #     1.2 / 5.5 = 0.2182  # cp
    #     1.2 / 5.5 = 0.2182  # cmp
    #     0.6 / 5.5 = 0.1091  # byp
    #     4.5 / 5.5 = 0.8182  # sram
    #

    s.alpha_mul  = 1.00  # dynamic power (relative to mul)
    s.alpha_alu  = 0.33  # dynamic power (relative to mul)
    s.alpha_cp   = 0.22  # dynamic power (relative to mul)
    s.alpha_cmp  = 0.22  # dynamic power (relative to mul)
    s.alpha_byp  = 0.11  # dynamic power (relative to mul)
    s.alpha_sram = 0.82  # dynamic power (relative to mul)

    s.alpha_phi  = s.alpha_cp
    s.alpha_br   = s.alpha_cmp

    # gamma
    #
    # gamma is the fraction of total tile power that is due to static
    # leakage power when executing a multiply at nominal voltage. Tiles
    # are homogeneous, so the leakage of each tile is the same regardless
    # of what the tile is executing dynamically.

    s.gamma = 0.1

    # beta
    #
    # beta is the ratio of leakage current in a 2kB SRAM bank compared to
    # the leakage current in a tile.

    s.beta = 2.0

    # s captures the power-law relationship between power and voltage.
    # Note that s does not include the fact that frequency is also a
    # function of voltage. So the classic cubic relationship between power
    # and voltage would mean setting s to 2.0.

    s.s = 2.0

    # throughput and latency
    #
    # This is the throughput through the CGRA in iterations per cycle. We
    # use the cycle-level simulator to measure throughput through the
    # graph.
    #
    # The latency is the time it takes for the CGRA to complete 1000
    # iterations. This is in units of nominal voltage cycles.

    #perf = s.sim.calc_performance()
    perf = { 'throughput': 0, 'latency': 0 }

    s.throughput = perf['throughput']
    s.latency    = perf['latency']

    # Power constraint.
    #
    # This is the total power available for _allocation_ among active
    # tiles and srams. Inactive tiles and srams are power-gated, and this
    # power is available for allocation to active tiles and srams.
    #
    # The power constraint is therefore calculated by summing the powers
    # of active tiles and active sram banks at nominal voltage and
    # frequency.

    s.P_alloc = s.N_T * s.P_tile_total( s.V_N, 'mul' ) \
              + s.N_S * s.P_sram_total( s.V_N )

  # f
  #
  # A rough approximation of frequency vs voltage
  #

  def f( s, V ):
    return -1161.6 * V**2 + 4056.9 * V - 1689.1

  # T
  #
  # Look up the cycle time (normalized to nominal) for a given voltage.
  #

  def T( s, V ):
    if V == conf_dvfs['nominal']['V']: return conf_dvfs['nominal']['T']
    if V == conf_dvfs['fast'   ]['V']: return conf_dvfs['fast'   ]['T']
    if V == conf_dvfs['slow'   ]['V']: return conf_dvfs['slow'   ]['T']
    assert False, 'Voltage %f is not a valid mode in conf_dvfs' % V

  # I_L
  #
  # I_L is the leakage current of the tile. Here is the algebra for
  # calculating I_L, starting from the definition of gamma as the
  # fraction of total tile power that is due to static power (when
  # executing a multiply at nominal voltage).
  #
  #     gamma = P_tile_static / ( P_tile_static + P_tile_dynamic )
  #
  #     P_tile_static = ( gamma * P_tile_dynamic ) / ( 1 - gamma )
  #
  #     V * I_L       = ( gamma * P_tile_dynamic ) / ( 1 - gamma )
  #
  #     I_L           = ( gamma * P_tile_dynamic ) / ( V * ( 1 - gamma ) )
  #
  # Note that I_L is a constant that does not depend on the tile
  # operation. I_L is calculated from P_tile_dynamic at nominal voltage
  # executing a multiply op.
  #

  def I_L( s ):
    return \
      ( s.gamma * s.P_tile_dynamic( s.V_N, 'mul' ) ) / ( s.V_N * ( 1 - s.gamma ) )

  # alpha
  #
  # Dynamic power factors relative to a multiply

  def alpha( s, op ):
    alpha_dict = {
      'mul'   : s.alpha_mul,
      'alu'   : s.alpha_alu,
      'cp'    : s.alpha_cp,
      'cmp'   : s.alpha_cmp,
      'byp'   : s.alpha_byp,
      'sram'  : s.alpha_sram,
      'phi'   : s.alpha_phi,
      'br'    : s.alpha_br,
      'const' : 0.0, # hack to prevent constant nodes from being modeled as srams
      'zero'  : 0.0,
    }
    return alpha_dict[op]

  # Tile power
  #
  # - P_tile_static depends on V (linear)
  #
  # - P_tile_dynamic depends on V (quadratic) and f (linear with V) and op
  # (different power depending on what op this tile is configured to
  # execute). This also depends on the throughput of the entire CGRA. If
  # the CGRA is running at 0.5 throughput, then dynamic power is cut in
  # half (ignoring dynamic stall energy). However, leakage will begin to
  # add up.
  #

  def P_tile_static( s, V ):
    return V * s.I_L()

  def P_tile_dynamic( s, V, op ):
    return s.alpha(op) * s.throughput * s.f(V) * V**s.s

  def P_tile_total( s, V, op ):
    return s.P_tile_static( V ) + s.P_tile_dynamic( V, op )

  def E_tile_total( s, V, op ):
    return s.P_tile_total( V, op ) * s.latency

  # SRAM

  def P_sram_static( s, V ):
    return V * s.I_L() * s.beta

  def P_sram_dynamic( s, V ):
    return s.alpha('sram') * s.throughput * s.f(V) * V**s.s

  def P_sram_total( s, V ):
    return s.P_sram_static( V ) + s.P_sram_dynamic( V )

  def E_sram_total( s, V ):
    return s.P_sram_total( V ) * s.latency

  # CGRA Power

  def P_cgra_static_tiles( s ):
    P_s = 0.0
    for n in s.nodes:
      if s.verbose:
        print( '    - Tile Psta {:<20} : {:20.2f}'.format( str(n.name) + ' ' + str(n.V) + 'V', s.P_tile_static( n.V ) ) )
      P_s += s.P_tile_static( n.V )
    return P_s

  def P_cgra_static_srams( s ):
    P_s = 0.0
    for n in s.l_nodes:
      if s.verbose:
        print( '    - Sram Psta {:<20} : {:20.2f}'.format( str(n.name) + ' ' + str(n.V) + 'V', s.P_sram_static( n.V ) ) )
      P_s += s.P_sram_static( n.V )
    return P_s

  def P_cgra_dynamic_tiles( s ):
    P_d = 0.0
    for n in s.nodes:
      if s.verbose:
        print( '    - Tile Pdyn {:<20} : {:20.2f}'.format( str(n.name) + ' ' + n.op + ' ' + str(n.V) + 'V', s.P_tile_dynamic( n.V, n.op ) ))
      P_d += s.P_tile_dynamic( n.V, n.op )
    return P_d

  def P_cgra_dynamic_srams( s ):
    P_d = 0.0
    for n in s.l_nodes:
      if s.verbose:
        print( '    - Sram Pdyn {:<20} : {:20.2f}'.format( str(n.name) + ' ' + str(n.V) + 'V', s.P_sram_dynamic( n.V ) ) )
      P_d += s.P_sram_dynamic( n.V )
    return P_d

  def P_cgra_static( s ):
    if s.verbose:
      static_t = s.P_cgra_static_tiles()
      static_s = s.P_cgra_static_srams()
      total    = static_t + static_s
      print( '  - ^-- CGRA Pstatic tiles : {:20.2f}'.format( static_t ) )
      print( '  - CGRA Pstatic srams : {:20.2f}'.format( static_s ) )
      return total
    return s.P_cgra_static_tiles() + s.P_cgra_static_srams()

  def P_cgra_dynamic( s ):
    if s.verbose:
      dynamic_t = s.P_cgra_dynamic_tiles()
      dynamic_s = s.P_cgra_dynamic_srams()
      total    = dynamic_t + dynamic_s
      print( '  - ^-- CGRA Pdynamic tiles : {:20.2f}'.format( dynamic_t ) )
      print( '  - CGRA Pdynamic srams : {:20.2f}'.format( dynamic_s ) )
      return total
    return s.P_cgra_dynamic_tiles() + s.P_cgra_dynamic_srams()

  def P_cgra_tiles( s ):
    return s.P_cgra_static_tiles() + s.P_cgra_dynamic_tiles()

  def P_cgra_srams( s ):
    return s.P_cgra_static_srams() + s.P_cgra_dynamic_srams()

  def P_cgra_total( s ):
    if s.verbose:
      static = s.P_cgra_static()
      print( '- CGRA Pstatic  : {:20.2f}'.format( static ) )
      dynamic = s.P_cgra_dynamic()
      print( '- CGRA Pdynamic : {:20.2f}'.format( dynamic ) )
      total = static + dynamic
      print( '- CGRA Ptotal   : {:20.2f}'.format( total ) )
      return total
    return s.P_cgra_static() + s.P_cgra_dynamic()

  # CGRA Energy

  def E_cgra_static_tiles( s ):
    return s.P_cgra_static_tiles() * s.latency

  def E_cgra_static_srams( s ):
    return s.P_cgra_static_srams() * s.latency

  def E_cgra_dynamic_tiles( s ):
    return s.P_cgra_dynamic_tiles() * s.latency

  def E_cgra_dynamic_srams( s ):
    return s.P_cgra_dynamic_srams() * s.latency

  def E_cgra_static( s ):
    return s.P_cgra_static() * s.latency

  def E_cgra_dynamic( s ):
    return s.P_cgra_dynamic() * s.latency

  def E_cgra_tiles( s ):
    return s.P_cgra_tiles() * s.latency

  def E_cgra_srams( s ):
    return s.P_cgra_srams() * s.latency

  def E_cgra_total( s ):
    if s.verbose:
      static = s.E_cgra_static()
      print( '- CGRA Estatic  : {:20.2f}'.format( static ) )
      dynamic = s.E_cgra_dynamic()
      print( '- CGRA Edynamic : {:20.2f}'.format( dynamic ) )
      total = static + dynamic
      print( '- CGRA Etotal   : {:20.2f}'.format( total ) )
      return total
    return s.P_cgra_total() * s.latency

  # Changing VF

  def calc_performance( s ):
    perf = s.sim.calc_performance()
    s.throughput = perf['throughput']
    s.latency    = perf['latency']

  def set_V_node( s, node_name, V ):
    s.g.get_node( node_name ).set_V( V )
    s.g.get_node( node_name ).set_T( s.T(V) )
    #print( 'setting', node_name, V, s.T(V) )

  def set_V_range( s, V_range ):
    for node_name, V in V_range.items():
      s.set_V_node( node_name, V )

  def set_op_range( s, op_range ):
    for node_name, op in op_range.items():
      s.g.get_node( node_name ).set_op( op )

  #-----------------------------------------------------------------------
  # Autosearch
  #-----------------------------------------------------------------------

  def group_nodes( s ):
    groups  = {}
    visited = []

    def is_singly_chained( node ):
      n_srcs = len( node.all_srcs() )
      n_dsts = len( node.all_dsts() )
      return n_srcs == 1 and n_dsts == 1

    nodes = s.g.all_nodes()
    count = 1

    for node_name in nodes:
      if node_name in visited:
        continue
      visited.append( node_name )
      node = s.g.get_node( node_name )
      if is_singly_chained( node ):
        # Add entire chain to the group
        groups[count] = [ node_name ]
        # Search forward
        current_node = node
        while True:
          next_node_name = list(current_node.all_dsts())[0]
          next_node      = s.g.get_node( next_node_name )
          visited.append( next_node_name )
          if is_singly_chained( next_node ):
            groups[count].append( next_node_name )
            current_node = next_node
          else:
            break
        # Search backward
        current_node = node
        while True:
          prev_node_name = list(current_node.all_srcs())[0]
          prev_node      = s.g.get_node( prev_node_name )
          visited.append( prev_node_name )
          if is_singly_chained( prev_node ):
            groups[count].append( prev_node_name )
            current_node = prev_node
          else:
            break
        count += 1

    all_grouped = reduce( lambda x, y: x+y, groups.values() )
    other_nodes = set( visited ).difference( set( all_grouped ) )

    for node_name in other_nodes:
      groups[count] = [ node_name ]
      count += 1

    # Check we got all the nodes

    #for k, v in groups.items():
    #  print( k, v )

    assert len( nodes ) == sum( [ len(l) for l in groups.values() ] ), \
      'Total nodes %s, but sum of group elements is %s' % \
        ( len( nodes ), sum( [ len(l) for l in groups.values() ] ) )

    return groups

  # set_V_group

  def set_V_group( s, group, mode ):
    if mode == 'r': V = 0.61
    if mode == 'n': V = 0.90
    if mode == 's': V = 1.23
    V_range = { node_name: V for node_name in group }
    s.set_V_range( V_range )

  # set_V_setting

  def set_V_setting( s, groups, setting ):
    for k in setting.keys():
      s.set_V_group( groups[k], setting[k] )

  # compare

  def compare( s ):

    _2_power      = s.P_cgra_total()
    _2_energy     = s.E_cgra_total()
    _2_throughput = s.throughput
    _2_latency    = s.latency

    results = {
      'throughput' :   _2_throughput / s._1_throughput,
      'speedup'    : s._1_latency    /   _2_latency,
      'power'      :   _2_power      / s._1_power,
      'eeff'       : s._1_energy     /   _2_energy,
    }

    if s.verbose:
      print()
      print( '{}: {:>15} -- {:20.2f}'.format( '1', 'throughput', s._1_throughput ) )
      print( '{}: {:>15} -- {:20.2f}'.format( '1', 'latency',    s._1_latency ) )
      print( '{}: {:>15} -- {:20.2f}'.format( '1', 'power',      s._1_power ) )
      print( '{}: {:>15} -- {:20.2f}'.format( '1', 'energy',     s._1_energy ) )
      print()
      print( '{}: {:>15} -- {:20.2f}'.format( '2', 'throughput', _2_throughput ) )
      print( '{}: {:>15} -- {:20.2f}'.format( '2', 'latency',    _2_latency ) )
      print( '{}: {:>15} -- {:20.2f}'.format( '2', 'power',      _2_power ) )
      print( '{}: {:>15} -- {:20.2f}'.format( '2', 'energy',     _2_energy ) )
      print()
      print( '{}: {:>15} -- {:20.2f}'.format( 'X', 'throughput', results['throughput'] ) )
      print( '{}: {:>15} -- {:20.2f}'.format( 'X', 'speedup',    results['speedup']    ) )
      print( '{}: {:>15} -- {:20.2f}'.format( 'X', 'power',      results['power']      ) )
      print( '{}: {:>15} -- {:20.2f}'.format( 'X', 'eeff',       results['eeff']       ) )
      print()

    return results

  # compare_group_setting

  def compare_group_setting( s, groups, setting ):

    s.set_V_setting( groups, setting )
    s.calc_performance()
    s.compare()

  # compare_node_setting

  def compare_node_setting( s, setting ):

    s.set_V_range( setting )
    s.calc_performance()
    s.compare()

  # extract_node_settings

  def extract_node_settings( s ):
    expanded_setting = \
      { node_name: s.g.get_node( node_name ).V \
          for node_name in s.g.all_nodes() }
    return expanded_setting

  def load_json_settings( s, json_f ):
    with open( json_f, 'r' ) as fd:
      setting = json.load( fd )
    s.set_V_range( setting )

  #-----------------------------------------------------------------------
  # Compiler Power-Mapping Algorithm -- As described in Paper Section III
  #-----------------------------------------------------------------------

  def autosearch( s, skip_search=False, prioritize_energy=False ):

    #---------------------------------------------------------------------
    # Phase 1: Complexity-Reduction Phase
    #---------------------------------------------------------------------

    groups = s.group_nodes()

    # Nominal

    setting_nominal = { k: 'n' for k in groups.keys() }
    s.set_V_setting( groups, setting_nominal )
    s.calc_performance()

    s._1_power      = s.P_cgra_total()
    s._1_energy     = s.E_cgra_total()
    s._1_throughput = s.throughput
    s._1_latency    = s.latency

    #---------------------------------------------------------------------
    # Phase 2: Energy-Delay-Optimization Phase
    #---------------------------------------------------------------------

    if skip_search:

      if not prioritize_energy:
        with open( s.g.json + '.pre.nodes', 'r' ) as fd:
          extracted_settings = json.load( fd )
      else:
        with open( s.g.json + '.pre.eeff.nodes', 'r' ) as fd:
          extracted_settings = json.load( fd )

    else:

      if not prioritize_energy:

        template = 'Group {g:3} of {gtot:3} : {perf:4.2f}x perf, {eeff:4.2f}x eeff -- {rest:48} {nom:48} -> chose [{chosen}]'

        results_tmpl = '[ {} : {:4.2f}x perf, {:4.2f}x eeff -- ({:4.2f}x, {:4.2f}x) ]'

        setting = { k: 's' for k in groups.keys() }

        s.set_V_setting( groups, setting )
        s.calc_performance()
        results = s.compare()
        print( '^-- comparison for (1) no DVFS, (2) initialized state, '
               'and (X) relative factor' )
        print()
        print( 'INITIALIZED -- ALL SPRINT --',
               '{:4.2f}x perf, {:4.2f}x eeff'.format(
                 results['throughput'], results['eeff'] ) )
        print()

        current_results = results

        def try_run( groups, setting ):
          s.set_V_setting( groups, setting )
          s.calc_performance()
          results = s.compare()
          return results

        s.verbose = False
        for k in sorted( groups.keys() ):
          rest_str = ''
          nom_str = ''
          done = False
          setting[k] = 'r'
          results = try_run( groups, setting )
          perf_diff = results['throughput'] / current_results['throughput']
          eeff_diff = results['eeff']       / current_results['eeff']
          rest_str  = results_tmpl.format( setting[k], \
                        results['throughput'], results['eeff'],
                        perf_diff, eeff_diff )
          if perf_diff * eeff_diff > 1.00: done = True
          if not done and perf_diff * eeff_diff < 1.07:
            setting[k] = 'n'
            results = try_run( groups, setting )
            perf_diff = results['throughput'] / current_results['throughput']
            eeff_diff = results['eeff']       / current_results['eeff']
            nom_str  = results_tmpl.format( setting[k], \
                         results['throughput'], results['eeff'],
                         perf_diff, eeff_diff )
            if perf_diff * eeff_diff > 1.00: done = True
            if not done and perf_diff * eeff_diff < 1.07:
              setting[k] = 's'
              s.set_V_setting( groups, setting )
          chosen_str = setting[k]
          if setting[k] != 's':
            current_results = results
          output_str = template.format(
            perf=current_results['throughput'],
            eeff=current_results['eeff'],
            g=k,
            gtot=len(groups.keys()),
            rest=rest_str,
            nom=nom_str,
            chosen=chosen_str,
          )
          print( output_str )
        print()

        s.verbose = True
        s.calc_performance()
        s.compare()

        # Dump mapping before bypass adjustment

        mapping = { k: { 'mode': setting[k], 'nodes': groups[k] } for k in groups.keys() }

        with open( s.g.json + '.pre.groups', 'w' ) as fd:
          json.dump( mapping, fd, sort_keys=True, indent=4,
            separators=(',', ': ') )

        extracted_settings = s.extract_node_settings()

        with open( s.g.json + '.pre.nodes', 'w' ) as fd:
          json.dump( extracted_settings, fd, sort_keys=True, indent=4,
            separators=(',', ': ') )

      else:

        template = 'Group {g:3} of {gtot:3} : {perf:4.2f}x perf, {eeff:4.2f}x eeff -- {rest:48} -> chose [{chosen}]'

        results_tmpl = '[ {} : {:4.2f}x perf, {:4.2f}x eeff -- ({:4.2f}x, {:4.2f}x) ]'

        setting = { k: 'n' for k in groups.keys() }

        s.set_V_setting( groups, setting )
        s.calc_performance()
        results = s.compare()
        print( '^-- comparison for (1) no DVFS, (2) initialized state, '
               'and (X) relative factor' )
        print()
        print( 'INITIALIZED -- ALL NOMINAL --',
               '{:4.2f}x perf, {:4.2f}x eeff'.format(
                 results['throughput'], results['eeff'] ) )
        print()

        current_results = results

        def try_run( groups, setting ):
          s.set_V_setting( groups, setting )
          s.calc_performance()
          results = s.compare()
          return results

        s.verbose = False
        for k in sorted( groups.keys() ):
          rest_str = ''
          done = False
          setting[k] = 'r'
          results = try_run( groups, setting )
          perf_diff = results['throughput'] / current_results['throughput']
          eeff_diff = results['eeff']       / current_results['eeff']
          rest_str  = results_tmpl.format( setting[k], \
                        results['throughput'], results['eeff'],
                        perf_diff, eeff_diff )
          if perf_diff * eeff_diff > 1.00: done = True
          if not done:
            setting[k] = 'n'
            s.set_V_setting( groups, setting )
          chosen_str = setting[k]
          if setting[k] != 'n':
            current_results = results
          output_str = template.format(
            perf=current_results['throughput'],
            eeff=current_results['eeff'],
            g=k,
            gtot=len(groups.keys()),
            rest=rest_str,
            chosen=chosen_str,
          )
          print( output_str )
        print()

        s.verbose = True
        s.calc_performance()
        s.compare()

        # Dump mapping before bypass adjustment

        mapping = { k: { 'mode': setting[k], 'nodes': groups[k] } for k in groups.keys() }

        with open( s.g.json + '.pre.eeff.groups', 'w' ) as fd:
          json.dump( mapping, fd, sort_keys=True, indent=4,
            separators=(',', ': ') )

        extracted_settings = s.extract_node_settings()

        with open( s.g.json + '.pre.eeff.nodes', 'w' ) as fd:
          json.dump( extracted_settings, fd, sort_keys=True, indent=4,
            separators=(',', ': ') )

    #---------------------------------------------------------------------
    # Phase 3: Constraint Phase -- for Physical Co-Location
    #---------------------------------------------------------------------

    # Group all nodes by tile

    tile_groups = {}
    for node_name in s.g.all_nodes():
      stripped_name = node_name.split('_byp')[0]
      if stripped_name not in tile_groups.keys():
        tile_groups[stripped_name] = []
      tile_groups[stripped_name].append( node_name )

    # Prep for pass

    if not prioritize_energy:

      template = 'Tile {g:3} of {gtot:3} : {perf:4.2f}x perf, {eeff:4.2f}x eeff -- {v:43} -> chose [{chosen}]'

      results_tmpl = '[ {} : ({:4.2f}x, {:4.2f}x) ]'

      setting = extracted_settings
      s.set_V_range( setting )
      s.calc_performance()
      results = s.compare()
      print( 'STARTING CONSTRAINT PHASE -- ',
             '{:4.2f}x perf, {:4.2f}x eeff'.format(
               results['throughput'], results['eeff'] ) )
      print()

      current_results = results

      def try_bypass_run( try_setting ):
        s.set_V_range( try_setting )
        s.calc_performance()
        results = s.compare()
        return results

      # Normalize within a tile to same VF

      s.verbose = False

      for tile_i, tiles in enumerate( tile_groups.values() ):

        nodes = [ s.g.get_node( node_name ) for node_name in tiles ]
        vfs   = [ node.V for node in nodes ]
        ops   = [ node.op for node in nodes ]

        # Get the possible vf options for this tile

        highest_vf = max( vfs )
        lowest_vf  = min( vfs )

        vdiff = lowest_vf - highest_vf
        if vdiff > -0.01 and vdiff < 0.01: # same
          print( 'skipping tile', tile_i+1 )
          continue

        vf_options = []
        if lowest_vf < 0.65:
          vf_options.append( 0.61 )
          if highest_vf < 0.95:
            vf_options.append( 0.90 )
          else:
            vf_options.append( 0.90 )
            vf_options.append( 1.23 )
        else:
          vf_options.append( 0.90 )
          vf_options.append( 1.23 )

        # Run each option

        v_str = ''
        results = {}
        ed_product = {}
        for vf in vf_options:
          new_setting = dict( setting )
          for node_name in tiles:
            new_setting[node_name] = vf
          results[vf] = try_bypass_run( new_setting )
          perf_diff = results[vf]['throughput'] / current_results['throughput']
          eeff_diff = results[vf]['eeff']       / current_results['eeff']
          ed_product[vf] = perf_diff * eeff_diff

        # Pick the option with the highest ED product

        max_ed = max( ed_product.values() )
        max_vf = 0
        for vf, value in ed_product.items():
          if max_ed >= 0.99*value:
            max_vf = vf

        # Make this the real VF setting for these nodes

        for node_name in tiles:
          setting[node_name] = max_vf

        current_results = results[max_vf]

        # Print

        for vf, value in ed_product.items():
          v_str += ' [ {}: {:4.2f} ]'.format( vf, value )

        output_str = template.format(
          perf=current_results['throughput'],
          eeff=current_results['eeff'],
          g=tile_i+1,
          gtot=len(tile_groups.keys()),
          v=v_str,
          chosen=max_vf,
        )
        print( output_str )

      s.verbose = True

  #      # Choose new vf
  #
  #      # Attempt #1
  #      #
  #      # All VF are lowest/highest
  #
  #      if version == 1:
  #        new_vf = highest_vf
  #
  #      for node in nodes:
  #        if node.V != new_vf:
  #          #if s.verbose: print '- adjust', node.name, 'to', new_vf
  #          s.set_V_node( node.name, new_vf )
  #
  #      # Attempt #2
  #      #
  #      # All VF are lowest/highest
  #
  #      if version == 2:
  #        new_vf = lowest_vf
  #
  #      # Attempt #3
  #      #
  #      # If VF are different, just make them all nominal
  #
  #      if version == 3:
  #        vdiff = lowest_vf - highest_vf
  #        if vdiff < -0.01 or vdiff > 0.01: # different
  #          new_vf = nominal_vf
  #        else: new_vf = highest_vf #same
  #
  #      # Attempt #4
  #      #
  #      # If VF are different, prioritize energy unless ops are cheap
  #
  #      if version == 4:
  #        vdiff = lowest_vf - highest_vf
  #        if vdiff < -0.01 or vdiff > 0.01: # different
  #          cheap = all( [ s.alpha( op ) < 0.4 for op in ops ] )
  #          if cheap : new_vf = highest_vf
  #          else     : new_vf = lowest_vf
  #        else: new_vf = highest_vf # same
  #
  #      # Adjust all nodes
  #      for node in nodes:
  #        if node.V != new_vf:
  #          #if s.verbose: print '- adjust', node.name, 'to', new_vf
  #          s.set_V_node( node.name, new_vf )

      s.calc_performance()
      s.compare()

      # Dump final mapping bypass adjustment

      extracted_settings = s.extract_node_settings()

      with open( s.g.json + '.final.nodes', 'w' ) as fd:
        json.dump( extracted_settings, fd, sort_keys=True, indent=4,
          separators=(',', ': ') )

      # Dump search results

      s.g.dump_vf_json()

    else:

      template = 'Tile {g:3} of {gtot:3} : {perf:4.2f}x perf, {eeff:4.2f}x eeff -- {v:43} -> chose [{chosen}]'

      results_tmpl = '[ {} : ({:4.2f}x, {:4.2f}x) ]'

      setting = extracted_settings
      s.set_V_range( setting )
      s.calc_performance()
      results = s.compare()
      print( 'STARTING CONSTRAINT PHASE -- ',
             '{:4.2f}x perf, {:4.2f}x eeff'.format(
               results['throughput'], results['eeff'] ) )
      print()

      current_results = results

      def try_bypass_run( try_setting ):
        s.set_V_range( try_setting )
        s.calc_performance()
        results = s.compare()
        return results

      # Normalize within a tile to same VF

      s.verbose = False

      for tile_i, tiles in enumerate( tile_groups.values() ):

        nodes = [ s.g.get_node( node_name ) for node_name in tiles ]
        vfs   = [ node.V for node in nodes ]
        ops   = [ node.op for node in nodes ]

        # Get the possible vf options for this tile

        highest_vf = max( vfs )
        lowest_vf  = min( vfs )

        vdiff = lowest_vf - highest_vf
        if vdiff > -0.01 and vdiff < 0.01: # same
          print( 'skipping tile', tile_i+1 )
          continue

        vf_options = [ 0.61, 0.90 ]

        # Run each option

        v_str = ''
        results = {}
        ed_product = {}
        for vf in vf_options:
          new_setting = dict( setting )
          for node_name in tiles:
            new_setting[node_name] = vf
          results[vf] = try_bypass_run( new_setting )
          perf_diff = results[vf]['throughput'] / current_results['throughput']
          eeff_diff = results[vf]['eeff']       / current_results['eeff']
          ed_product[vf] = perf_diff * eeff_diff

        # Pick the option with the highest ED product

        max_ed = max( ed_product.values() )
        max_vf = 0
        for vf, value in ed_product.items():
          if max_ed >= 0.99*value:
            max_vf = vf

        # Make this the real VF setting for these nodes

        for node_name in tiles:
          setting[node_name] = max_vf

        current_results = results[max_vf]

        # Print

        for vf, value in ed_product.items():
          v_str += ' [ {}: {:4.2f} ]'.format( vf, value )

        output_str = template.format(
          perf=current_results['throughput'],
          eeff=current_results['eeff'],
          g=tile_i+1,
          gtot=len(tile_groups.keys()),
          v=v_str,
          chosen=max_vf,
        )
        print( output_str )

      s.verbose = True

      s.calc_performance()
      s.compare()

      # Dump final mapping bypass adjustment

      extracted_settings = s.extract_node_settings()

      with open( s.g.json + '.final.eeff.nodes', 'w' ) as fd:
        json.dump( extracted_settings, fd, sort_keys=True, indent=4,
          separators=(',', ': ') )

      # Dump search results

      s.g.dump_vf_json( suffix='_dvfs_eeff' )

