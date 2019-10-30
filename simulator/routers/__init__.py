from simulator.utils.basic_utils import new_iterable, Timer
from simulator.utils.math_utils import combvec
import multiprocessing as mp
import pandas as pd

from .cgr import cgr_build_route_list_fast, cgr_build_route_list_slow
from .bfs import bfs_build_route_list_slow, bfs_build_route_list_fast

# ============================================================================================================
# === ROUTING FUNCTIONS. CALLED BY DtnBaseRouter and its subclasses to do the routers
# ============================================================================================================

def build_route_list(orig, dest, time, contact_plan, range_intervals, relays=None, max_speed=125,
                     verbose=True, ncpu=1, algorithm='bfs', mode='fast'):
    # Check inputs
    orig, dest, time = new_iterable(orig), new_iterable(dest), new_iterable(time)

    # Check the algorithm selected
    assert algorithm in ['bfs', 'cgr'], 'Algorithm parameter can only be "bfs" or "cgr". "{}" not valid'.format(
        algorithm)
    assert mode in ['fast', 'slow'], 'Mode must be "fast" or "slow". Current mode {} is not valid'.format(mode)

    # Merge the range intervals with the contact plan table
    contact_plan['range'] = [range_intervals.range[range_intervals.cid == cid].max() for cid in contact_plan.index]

    # Build route for each destination
    if ncpu == 1:
        data = _build_route_list_serial(orig, dest, time, contact_plan, range_intervals, relays=relays,
                                        max_speed=max_speed, verbose=verbose, mode=mode, algorithm=algorithm)
    else:
        data = _build_route_list_parallel(orig, dest, time, contact_plan, range_intervals, ncpu, relays=relays,
                                          max_speed=max_speed, verbose=verbose, mode=mode, algorithm=algorithm)

    # Format route schedule
    routes = pd.concat(data)
    if routes.empty: raise RuntimeError('NO ROUTES WERE COMPUTED')
    cols = ['time', 'orig', 'dest', 'route', 'EAT', 'contacts', 'tstart', 'tend', 'limit_cid', 'nhops']
    routes = routes[cols]

    # Sort data
    routes = routes.sort_values(by=['time', 'orig', 'dest', 'EAT', 'nhops', 'tstart', 'tend'])

    return routes.reset_index(drop=True)

def _build_route_list_serial(orig, dest, time, contact_plan, range_intervals, relays=None, max_speed=125,
                             verbose=True, mode='fast', algorithm='bfs'):
    # Initialize variables
    data = []

    # Select function to get routes
    fun = _select_routing_function(algorithm, mode)

    # Build route for each destination
    for o, d, t in combvec(orig, dest, time):
        if o == d: continue

        # Compute routes with/without logging
        if verbose == False:
            routes = fun(o, d, t, contact_plan, relays=relays, max_speed=max_speed, verbose=verbose)
        else:
            with Timer('{}, {}, {}'.format(o, d, t)):
                routes = fun(o, d, t, contact_plan, relays=relays, max_speed=max_speed, verbose=verbose)

        # Store routes
        data.append(pd.DataFrame(routes))

    return data

def _build_route_list_parallel(orig, dest, time, contact_plan, range_intervals, ncpu, relays=None,
                               max_speed=125, verbose=False, mode='fast', algorithm='bfs'):
    # Initialize pool of workers
    ncpu = min(mp.cpu_count()-1, ncpu)
    pool = mp.Pool(ncpu)

    # Select function to get routes
    fun = _select_routing_function(algorithm, mode)

    # Submit jobs and extract results
    kwds    = {'max_speed': max_speed, 'relays': relays, 'verbose':verbose}
    futures = {(o,d,t):pool.apply_async(fun, args=(o, d, t, contact_plan), kwds=kwds) for o, d, t in combvec(orig, dest, time) if o != d}

    # Collect results
    data = []
    for (o,d,t), f in futures.items():
        try:
            data.append(pd.DataFrame(f.get()))
        except Exception as e:
            e.args += ('Try inputs {}'.format((o,d,t)),)
            raise e

    # Clean up
    pool.close()

    return data

def _select_routing_function(algorithm, mode):
    if algorithm.lower() == 'cgr' and mode.lower() == 'fast':
        fun = cgr_build_route_list_fast
    elif algorithm.lower() == 'cgr' and mode.lower() == 'slow':
        fun = cgr_build_route_list_slow
    elif algorithm.lower() == 'bfs' and mode.lower() == 'fast':
        fun = bfs_build_route_list_fast
    elif algorithm.lower() == 'bfs' and mode.lower() == 'slow':
        fun = bfs_build_route_list_slow
    else:
        raise ValueError('Cannot select routers function wuith algorithm {} and mode {}'.format(algorithm, mode))
    return fun