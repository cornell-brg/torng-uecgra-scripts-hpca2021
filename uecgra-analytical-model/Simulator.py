#! /usr/bin/env python
#=========================================================================
# Simulator.py
#=========================================================================
# A discrete-event performance simulator that propagates message tokens
# through a given DFG.
#
# This model corresponds to Section II.A in the paper.
#
# Author : Christopher Torng
# Date   : August 13, 2019
#

from collections import deque

# Token
#
# Tokens represent data and live on wires. When placing data on a wire, we
# set the token. when pulling data off a wire, we unset the token.

class Token( object ):

  def __init__( s ):
    s.value       = False
    s.guard_begin = 0.0
    s.guard_span  = 0.0
    s.guard_set   = False

  def set( s, v ):
    s.value = v # use non-zero integer tokens for SimNode any/all to work

  def read( s ):
    return s.value

  def guarded_set( s, v, time, span ):
    s.value       = v
    s.guard_begin = time
    s.guard_span  = span
    s.guard_set   = True

  def guarded_read( s, time ):
    if s.guard_set:
      time_elapsed = time - s.guard_begin
      diff         = time_elapsed - s.guard_span
      # Accomodate floating-point precision (e.g., is 1.34 > 1.34 True or
      # False?)
      if diff > -0.001 :
        return s.value
    return False

  def deassert_guard( s ):
    s.guard_set = False

# SimNode
#
# A simulator node wraps the underlying node with simulator-related
# methods, including being able to 'tick', produce data onto wires, and
# consume data from wires.

class SimNode( object ):

  def __init__( s, node, verbose=False ):

    s.verbose = verbose

    s.node = node
    s.name = s.node.name

    s.n_srcs = len( s.node.all_srcs() )
    s.n_dsts = len( s.node.all_dsts() )

    # Flags for nodes producing live-ins or consuming live-outs

    s.live_in  = False
    s.live_out = False

    # Counter for sources (i.e., producing live-ins)
    #
    # Tokens start at 1 as valid values and increment

    s.token_counter = 1

    # Input queues

    s.queues = { src: deque( maxlen=2 ) for src in s.node.all_srcs() }
    s.shadow_queues = { src: deque( maxlen=2 ) for src in s.node.all_srcs() }
    s.pipeline = False # Enable pipeline behavior
    s.pipewait = False

    # Special token for live-out nodes, which have no fanout but still
    # need to wait for data to propagate (e.g., for sram write)

    s.live_out_token = Token()

    # Initialize first tick

    s.time = 0.0

  def reset( s ):
    s.token_counter = 1
    s.time = 0.0
    for k in s.queues.keys():
      s.queues[k].clear()
      s.shadow_queues[k].clear()
    s.pipewait = False

  def setup( s, nodes_fanout, wires_fanout, wires_fanin, shadow_fanout, shadow_fanin ):
    s.nodes_fanout  = nodes_fanout
    s.wires_fanout  = wires_fanout
    s.wires_fanin   = wires_fanin
    s.shadow_fanout = shadow_fanout
    s.shadow_fanin  = shadow_fanin

    if not s.shadow_fanin and s.shadow_fanout:
      s.live_in = True

    if s.shadow_fanin and not s.shadow_fanout:
      s.live_out = True

  def tick( s ):

    if s.verbose: print( s.time, ': (*)', s.name, 'tick' )

    # For all outputs that have finished propagating (i.e., guarded_read
    # succeeds), use this edge to try to write into the input queues of
    # the downstream nodes. If the guarded read fails, it represents the
    # case where data has not finished propagating. If the downstream
    # queue is full, it represents a "not ready" signal for this cycle,
    # which stalls this node.

    for dst in s.wires_fanout:
      token       = s.wires_fanout[dst]
      token_value = token.guarded_read( time=s.time )

      if not token_value:
        if s.verbose: print( s.time, ':', s.name, 'found not ready --', dst )
        continue

      # Check if the downstream queue for this output was ready this
      # cycle. If it was ready, then this token pushes into the downstream
      # queue and the token is consumed.

      downstream_node = s.nodes_fanout[dst]

      if downstream_node.ready( time=s.time, src=s.name ):
        if s.verbose: print( s.time, ':', s.name, 'found ready --', downstream_node.name )
        if s.verbose: print( s.time, ':', s.name, 'trying to push to', downstream_node.name )
        downstream_node.push( time=s.time,
                              src=s.name,
                              token_value=token_value )
        token.set( False )            # consume
        token.deassert_guard()        # tokens
        token = s.shadow_fanout[dst]  #
        token.set( False )            #
        token.deassert_guard()        #
        s.pipewait = True

    # Dequeue from the input queues if all fanout tokens are gone

    if not s.live_out:
      fanout_empty = all( [ t.read()==False for t in s.wires_fanout.values() ] )
      peek_values = [ q[-1] if q else False for q in s.queues.values() ]
      if peek_values and all( peek_values ):
        if fanout_empty:
          # Dequeue the front of the input queues
          if s.verbose: print( s.time, ':', s.name, 'pushed everything, popping input queues' )
          for k in s.queues.keys():
            s.queues[k].pop()
            s.shadow_queues[k].pop()
          # Try to fire another token if we are ready
          peek_values = [ q[-1] if q else False for q in s.queues.values() ]
          if peek_values and all( peek_values ):
            max_val = max( peek_values )
            s.fire( time=s.time, token_value=max_val )

    # Special handling for live-out nodes, which have no fanout but still
    # need to wait for data to propagate (e.g., for sram write)

    if s.live_out:
      if s.live_out_token.guarded_read( time=s.time ):
        if s.verbose: print( s.time, ':', s.name, 'sinking token', s.live_out_token.read() )
        s.live_out_token.set( False )     # consume
        s.live_out_token.deassert_guard() # token
        # Dequeue the front of the input queues
        for k in s.queues.keys():
          if s.queues[k]:
            s.queues[k].pop()
          if s.shadow_queues[k]:
            s.shadow_queues[k].pop()
        s.pipewait = True
        # Try to fire another token if we are ready
        peek_values = [ q[-1] if q else False for q in s.queues.values() ]
        if peek_values and all( peek_values ):
          max_val = max( peek_values )
          s.fire( time=s.time, token_value=max_val )

    # If not all tokens have finished sending, then wait..

    # If this is a source, then set up the next token

    if s.live_in:
      # Check if we need to send the next token
      token_fanout = [ t.read() for t in s.shadow_fanout.values() ]
      produce_not_done = any( token_fanout )
      if produce_not_done: return
      # Send the next token
      token_value = s.token_counter
      if s.verbose: print( s.time, ':', s.name, 'sending live in token', token_value )
      for token in s.shadow_fanout.values():
        token.guarded_set( v=token_value, time=s.time, span=s.node.T )
      s.token_counter += 1

  def ready( s, time, src ):

    if s.verbose: print( time, ':', s.name, 'checking ready for', src, s.queues )

    # Check for backpressure in the queue. If we have already pushed a
    # token to this node, the queue will be full.

    if src != None:
      if s.verbose: print( time, ':', s.name, 'checking backpressure', src, s.queues )
      if len( s.queues[src] ) == s.queues[src].maxlen :
        return False

      if not s.pipeline and len( s.queues[src] ) == s.queues[src].maxlen - 1 and s.pipewait:
        if s.verbose: print( time, ':', s.name, 'pipewait', src )
        return False

      if s.verbose: print( time, ':', s.name, 'backpressure passed' )

    if s.verbose: print( time, ':', s.name, 'is ready for', src )

    return True

  def push( s, time, src, token_value ):

    if s.verbose: print( time, ':', s.name, 'pushing token', token_value )

    s.shadow_queues[src].appendleft( token_value )

    # Check whether all input data is ready (i.e., when all tokens
    # in the input queues are set)

    peek_values = [ q[-1] if q else False for q in s.shadow_queues.values() ]

    consume_ready = all( peek_values )

    if not consume_ready:
      return

    # Fire node
    #
    # Only fire the node if we just enqueued into an empty queue. If the queue
    # was not empty, then we are just buffering.

    max_val = max( peek_values )

    if len( s.shadow_queues[src] ) == 1:
      s.fire( time=time, token_value=max_val )

  # fire

  def fire( s, time, token_value ):

    # Push a token toward each downstream node. Send the max of all
    # input tokens, representing the latest iteration count.

    if s.verbose: print( time, ':', s.name, 'firing token', token_value, 'with guard', s.node.T )

    for token in s.shadow_fanout.values():
      token.guarded_set( v=token_value, time=time, span=s.node.T )

    # Special handling for live-out nodes, which have no fanout but still
    # need to wait for data to propagate (e.g., for sram write)

    if s.live_out:
      s.live_out_token.guarded_set( v    = token_value,
                                    time = time,
                                    span = s.node.T )

# Simulator
#
# The simulator is an event-based simulator. Given a graph, the simulator
# creates a SimNode for each node and wires for all edges. Then the
# simulator runs by advancing time and ticking the nodes in reverse
# topological order (to model hardware for input-registered nodes).

class Simulator( object ):

  def __init__( s, graph, verbose=False, do_plot=False ):

    s.g = graph

    s.verbose = verbose
    s.do_plot = do_plot

    # Track how many times we have run simulation so we can tag outputs

    s.run_counter = 0

    #---------------------------------------------------------------------
    # Time
    #---------------------------------------------------------------------

    s.global_time = 0.0

    #---------------------------------------------------------------------
    # Wire delay mode
    #---------------------------------------------------------------------
    # If wire delays were not modeled, then all wires have zero-delay
    # timing and two ticks that are 0.0001 apart can zoom data through
    # both.
    #
    # With wire delays modeled, wires have time guards modeling critical
    # paths with length equal to the producer node's T. So when T changes
    # due to DVFS, the critical path also changes. If a consumer node
    # tries to pop a token from a wire before the time guard is released,
    # the consumer node pop fails.

    #---------------------------------------------------------------------
    # Nodes
    #---------------------------------------------------------------------

    # Create simulator nodes from graph nodes

    s.sim_nodes = {}

    for node_name in s.g.all_nodes():
      node = s.g.get_node( node_name )
      s.sim_nodes[ node_name ] = \
        SimNode( node, verbose=s.verbose )

    # Each sim node has a pointer to downstream sim nodes

    s.nodes_fanout = {}

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      s.nodes_fanout[name] = \
        { dst: s.sim_nodes[dst] for dst in sim_node.node.all_dsts() }

    #---------------------------------------------------------------------
    # Wires
    #---------------------------------------------------------------------

    # Set up wires between nodes + Double buffer for cycle-level simulator
    #
    # - Why double-buffer. Why not just go in reverse-topo order? Because
    # there _will_ be cycles in the graph. We cannot guarantee that we
    # will not "race" a token through multiple nodes in one cycle due to
    # order of execution.
    #
    # These wires transfer data from the previous upstream node.
    # When all inputs are ready (i.e., the tokens on the wires are all
    # set), the node fires, pulling all the tokens off the input wires
    # and setting the tokens on each output wire.
    #
    # The shadow wires are the double buffers to enable correct behavior
    # in cycle-level simulation. On each tick, sim nodes will only ever
    # read from the real wires and write into the shadow wires. This
    # prevents data from "racing through" multiple nodes in zero time.
    # When time advances, all data on the shadow wires are copied into the
    # real wires to represent data propagation.
    #

    s.shadow_fanout = {}
    s.shadow_fanin  = {}
    s.wires_fanout  = {}
    s.wires_fanin   = {}

    # A wire is an entry in this dictionary. A value of False within the
    # token means the token is not set. A value of True means the token is
    # set.

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      s.wires_fanout[name] = \
        { dst: Token() for dst in sim_node.node.all_dsts() }

    # Create aliases for fanin from the fanout wires for convenience

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      s.wires_fanin[name] = \
        { src: s.wires_fanout[src][name] for src in sim_node.node.all_srcs() }

    # Create a set of shadow wires for double-buffered simulation

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      s.shadow_fanout[name] = \
        { dst: Token() for dst in sim_node.node.all_dsts() }

    # Create aliases for fanin from the shadow fanout wires for convenience

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      s.shadow_fanin[name] = \
        { src: s.shadow_fanout[src][name] for src in sim_node.node.all_srcs() }

    # Set up the wires for each sim node

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      sim_node.setup( nodes_fanout  = s.nodes_fanout[name],
                      wires_fanout  = s.wires_fanout[name],
                      wires_fanin   = s.wires_fanin[name],
                      shadow_fanout = s.shadow_fanout[name],
                      shadow_fanin  = s.shadow_fanin[name] )

    #---------------------------------------------------------------------
    # Priority queue that tracks ticks
    #---------------------------------------------------------------------
    # Quick and dirty priority queue

    class PriorityQueue:
      def __init__( s, order ):
        s.order     = order
        s.container = []
      def add( s, time, name ):
        s.container.append( ( time, name ) )
        s.container = sorted( s.container, reverse=True, \
          key = lambda x: ( x[0], s.order.index(x[1]) ) )
      def pop( s ):
        time, name = s.container[-1]
        del( s.container[-1] )
        return time, name
      def empty( s ):
        return len( s.container ) == 0

    # Tick in reverse topological order

    order = s.g.topological_sort()[::-1]
    s.pq  = PriorityQueue( order )

    # Reset

    s.reset()

  # reset
  #
  # - Any recurrence wires need to be initialized with a token
  # - Any phi nodes are also initialized with a token
  #

  def reset( s ):

    s.global_time = 0.0

    # Reset the sim nodes

    for sim_node in s.sim_nodes.values():
      sim_node.reset()

    # Reset the wires

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      for token in s.wires_fanout[name].values():
        token.set( False )

    # Reset the shadow wires

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      for token in s.shadow_fanout[name].values():
        token.set( False )

    # Initialize recurrence wires

    for edge in s.g.recurrence_edges:
      src, dst = edge
      s.shadow_fanout[src][dst].guarded_set( 1, s.global_time, 0.0 )
      s.wires_fanout[src][dst].guarded_set( 1, s.global_time, 0.0 )

    # Initialize phi nodes

    for sim_node in s.sim_nodes.values():
      name = sim_node.name
      if sim_node.node.op == 'phi':
        for token in s.shadow_fanout[name].values():
          token.guarded_set( 1, s.global_time, sim_node.node.T )
        for token in s.wires_fanout[name].values():
          token.guarded_set( 1, s.global_time, sim_node.node.T )

  # run
  #
  # Run simulation
  #

  def run( s, run_id, max_tokens = 10, max_time = 100000.0 ):
#  def run( s, run_id, max_tokens = 10, max_time = 20.0 ):

    # Put all nodes at their default time into the priority queue

    for sim_node in s.sim_nodes.values():
      s.pq.add( sim_node.time, sim_node.name )

    # Track the token counter on any live-in node to know when to stop

    live_in_node = \
      [ n for n in s.sim_nodes.values() if n.live_in ][0]

    token_count = live_in_node.token_counter

    # Simulate for some time

    while not s.pq.empty() and token_count <= max_tokens:

      # Time out

      if s.global_time > max_time:
        print( 'Error: Timed out' )
        break

      # If time has passed, copy the shadow wires to the real wires

      time, name = s.pq.pop()

      if time > s.global_time:
        # Copy shadow wires to real wires
        for sim_node in s.sim_nodes.values():
          sim_node_name = sim_node.name
          for k, token in s.shadow_fanout[sim_node_name].items():
            s.wires_fanout[sim_node_name][k].value       = token.value
            s.wires_fanout[sim_node_name][k].guard_begin = token.guard_begin
            s.wires_fanout[sim_node_name][k].guard_span  = token.guard_span
            s.wires_fanout[sim_node_name][k].guard_set   = token.guard_set
        # Copy shadow queues to real queues
        for sim_node in s.sim_nodes.values():
          sim_node_name = sim_node.name
          for k, q in sim_node.shadow_queues.items():
            sim_node.queues[k].clear()
            for entry in q:
              sim_node.queues[k].append( entry )
        # Clear pipe waits for input queues
        for sim_node in s.sim_nodes.values():
          sim_node.pipewait = False
        # Plot
        if s.do_plot and s.global_time <= 20.0:
          s.plot( dot_title = 'time='+str(s.global_time),
                  dot_f     = str(s.global_time)+'.'+run_id+'.dot'  )
        # Update time
        s.global_time = time

      sim_node = s.sim_nodes[ name ]
      sim_node.tick()
      sim_node.time += sim_node.node.T # Advance node time
      # Special tweak -- to make sprinting at 0.66 clock period be
      # synchronous every 3 cycles...
      # - E.g., three cycles of 0.66 = 1.98 -> convert to 2.00 to match
      # the intuition of a rationally divided clock
      if sim_node.node.T == 0.66 and str(sim_node.time).endswith('.98'):
        sim_node.time = round( sim_node.time )
      s.pq.add( sim_node.time, sim_node.name )

      token_count = live_in_node.token_counter

  # calc_performance
  #
  # Measure performance

  def calc_performance( s ):

    s.reset()

    # Run for a long time to amortize any startup overhead

    run_id = 'r' + str( s.run_counter )
    s.run( run_id = run_id, max_tokens = 50 )
    s.run_counter += 1

    # Read the token counter on any live-in node

    live_in_node = \
      [ n for n in s.sim_nodes.values() if n.live_in ][0]

    token_count = live_in_node.token_counter

    # MUST run long enough for any startup overhead to be amortized

    throughput = token_count / s.global_time
    latency    = s.global_time

    return { 'throughput': throughput, 'latency': latency }

  # calc_ii
  #
  # Measure ii (i.e., initiation interval ii)

  def calc_ii( s ):
    throughput = s.calc_performance()['throughput']
    ii         = 1.0 / throughput
    return ii

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
      '{dot_id} [ fontsize=24, width=2, ' \
      'penwidth=2, label="{name}\n{label}", ' \
      'style=filled, fillcolor={color} ];'

    edge_template = \
      '{src_dot_id}:s -> {dst_dot_id}:n ' \
      '[ arrowsize=2, penwidth=2, color={color}, label="  {token}" ];'

    # Loop over all nodes and generate a graphviz node declaration

    dot_nodes = []

    for sim_node in s.sim_nodes.values():
      fill        = '  '.join([ '.'*len(q) for q in sim_node.queues.values() ])
      peek_values = [ q[-1] if q else False for q in sim_node.queues.values() ]
      node_name          = sim_node.name
      node_cfg           = {}
      node_cfg['dot_id'] = node_name
      node_cfg['name']   = fill + '\n' + str(node_name)
      node_cfg['label']  = sim_node.node.label
      node_cfg['color']  = 'bisque' if any( peek_values ) \
                                    else 'white'

      dot_nodes.append( node_template.format( **node_cfg ) )

    # Loop over all edges and generate graphviz edge commands

    dot_edges = []

    for sim_node in s.sim_nodes.values():
      src = sim_node.name
      for dst, token in s.shadow_fanout[src].items():
        token_value = token.read()
        e_cfg = {}
        e_cfg['src_dot_id']  = src
        e_cfg['dst_dot_id']  = dst
        e_cfg['color']       = 'red' if token_value else 'black'
        e_cfg['token']       = token_value

        dot_edges.append( edge_template.format( **e_cfg ) )

    # Write out the graphviz dot graph file

    with open( dot_f, 'w' ) as fd:
      graph_cfg = {}
      graph_cfg['title'] = dot_title
      graph_cfg['nodes'] = '\n'.join( dot_nodes )
      graph_cfg['edges'] = '\n'.join( dot_edges )
      fd.write( graph_template.format( **graph_cfg ) )








