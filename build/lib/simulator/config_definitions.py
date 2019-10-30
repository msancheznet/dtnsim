""" This file contains the definitions for all sections acceptable in a simulator
    configuration file (.yaml).

    Each section has:
        1) Name
        2) Mandatory: If True, then a configuration file must have it
        3) Options: The set of options that can be specified
        4) Defvals: The default values for all or a subset of the options

    Note: A section that is **not mandatory** need not be specified in this file. If it
          is not, it still be parsed, but no checking of the provided parameters or
          default values will be set automatically.
"""
definitions = {
    'globals':
        {
         'mandatory': True,
         'options': {'id','indir', 'outdir', 'outfile', 'logfile', 'log', 'monitor', 'track',
                     'track_dt', 'export_monitor', 'validate'},
         'defvals': {'id': 'Simulation', 'outfile': 'Results.csv', 'logfile': 'Sim Log.log', 'log': False,
                     'monitor': True, 'track': True, 'track_dt': 1, 'export_monitor': False,
                     'validate': False}
        },
    'network':
        {
         'mandatory': True,
         'options': {'nodes', 'connections'},
         'defvals': {}
        },
    'scenario':
        {
         'mandatory': True,
         'options': {'epoch', 'seed', 'until'},
         'defvals': {'seed': None, 'until': None}
        },
    'node':
        {
         'mandatory': False,
         'options': {'class', 'relay', 'router', 'generators', 'selector', 'radios'},
         'defvals': {'class': 'DtnNode', 'relay': True, 'selector': 'DtnDefaultSelector'}
        },
    'radio':
        {
         'mandatory': False,
         'options': {'class', 'rate', 'BER', 'J_bit'},
         'defvals': {'BER': 0.0, 'J_bit': 1.0}
        },
    'markov_generator':
        {
         'mandatory': False,
         'options': {'class', 'file', 'min_bundle_size', 'max_bundle_size', 'latency_fraction'},
         'defvals': {'min_bundle_size': 8192, 'max_bundle_size': 4.096e6, 'latency_fraction': 0.5,
                     'class': 'DtnMarkovBundleGenerator'}
        },
    'bfs_centralized':
        {
         'mandatory': False,
         'options': {'class', 'routes', 'links', 'trajectories', 'router_mode', 'recompute_routes',
                     'excluded_routes', 'max_relay_hops', 'num_cores', 'max_crit',
                     'max_speed', 'algorithm'},
         'defvals': {'router_mode': 'fast', 'recompute_routes': False, 'num_cores': 1, 'max_crit': None,
                     'class': 'DtnRouter', 'max_speed': 40.0, 'routes': None, 'algorithm': 'bfs'}
        },
    'cbr_generator':
        {
         'mandatory': False,
         'options': {'class', 'rate', 'duration', 'bundle_size', 'tstart', 'critical', 'destination',
                     'origin', 'data_type', 'bundle_TTL'},
         'defvals': {'tstart': 0}
        },
    'file_generator':
        { 
         'mandatory': False,
         'options': {'class', 'bundle_size', 'tstart', 'critical', 'destination', 'origin', 'data_type',
                     'bundle_TTL', 'size'},
         'defvals': {'tstart': 0}
        }
}