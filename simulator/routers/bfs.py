from copy import deepcopy
import numpy as np
import pandas as pd
from .utils import isin, str_type

# ============================================================================================================
# === BFS SEARCH OF ROUTES
# ============================================================================================================

def backtrace(parent, start, end):
    path = [end]
    while path[-1] != start: path.append(parent[path[-1]])
    path.reverse()
    return tuple(path)

def bfs_build_route_list_slow(orig, dest, t, contact_plan, relays=None, max_speed=40.0, verbose=False):
    # Initialize variables
    cp     = contact_plan.copy(deep=True)
    tinf   = max(cp.tstart.max(), cp.tend.max()) + 100 * 365 * 24 * 3600
    nodes  = set(cp.orig).union(set(cp.dest))
    relays = relays if relays is not None else nodes

    # Eliminate contact with itself if it exists (needs to be done before adding -1 and -2)
    cp = cp.loc[~(cp.orig == cp.dest)]

    # Add dummy initial and final contacts: (orig, dest, tstart, tend, duration, range, rate, capacity
    cp.loc[-1, :] = (orig, orig, t, t, 0.0, 0.0, np.inf, np.inf)
    cp.loc[-2, :] = (dest, dest, np.inf, np.inf, 0.0, 0.0, np.inf, np.inf)
    cp = cp.sort_values(['tstart', 'tend', 'orig', 'dest'])

    # Initialize necessary data structures
    cp['EAT']    = tinf
    cp['owlt']   = cp['range']
    cp['margin'] = ((1.0 * max_speed / 3600) * cp.owlt) / 186282
    cp.loc[-1, 'EAT'] = t

    # Initialize variables
    queue   = []
    paths   = []
    EATs    = {}
    visited_nodes = {}
    found_paths   = []

    # Start at the root contact
    queue.append(-1)
    paths.append((-1,))
    visited_nodes[(-1,)] = {orig}
    EATs[(-1,)] = t

    # While there are contacts to explore
    while queue:
        # Get the next contact
        current, path = cp.loc[queue.pop(), :], paths.pop()

        # Find path properties
        visited = visited_nodes[path]
        EAT     = EATs[path]

        # Find the neighbors
        cids = (current.dest == cp.orig) & (~cp.dest.isin(visited)) & (cp.tend > EAT) & \
               (cp.dest.isin(relays) | (cp.dest == dest))

        # If no neighbors identified, continue
        if not cids.any(): continue

        # Compute early transmission time (ETT) and early arrival time (EAT) for neighbors
        ETT = cp.tstart[cids].apply(lambda x: max(x, EAT))
        EAT = ETT + cp.owlt[cids] + cp.margin[cids]

        # Iterate over neighbors
        for cid, _ in cp.loc[cids, :].iterrows():
            # Create a record for this path
            p = list(deepcopy(path))
            p.append(cid)
            p = tuple(p)

            # If next neighbor is destination, save path
            if cid == -2:
                found_paths.append(p)
                if verbose: print('New path: ' + str(p))
                continue

            # Store neighbors EAT
            EATs[p] = EAT.loc[cid]

            visited_nodes[p] = visited | {current.dest} # Do not use ADD, it does not return anything

            # Append the neighbor to continue exploring the graph
            queue.append(cid)
            paths.append(p)

    # Initialize variables
    routes = []

    # Iterate over computed paths
    for path in found_paths:
        # Get the route (i.e. nodes traversed
        path1 = path[1:]
        rt = tuple(cp.loc[idx, 'orig'] for idx in path1)

        # Get path contact list and EAT
        path2 = path[1:-1]
        end   = [cp.loc[idx, 'tend'] for idx in path2]
        ix    = np.argmin(end)

        # Compose route data structure
        route = {}
        route['orig']      = orig
        route['dest']      = dest
        route['time']      = t
        route['contacts']  = path2
        route['route']     = rt
        route['tstart']    = cp.loc[route['contacts'][0], 'tstart']
        route['tend']      = end[ix]
        route['EAT']       = EATs[path[:-1]]
        route['limit_cid'] = path2[ix]
        route['nhops']     = len(rt)-1
        routes.append(route)

    return routes

def bfs_build_route_list_fast(orig, dest, t, contact_plan, relays=None, max_speed=40.0, verbose=False):
    # Initialize variables
    cp     = contact_plan.copy(deep=True)
    tinf   = max(cp.tstart.max(), cp.tend.max()) + 100 * 365 * 24 * 3600
    nodes  = set(cp.orig).union(set(cp.dest))
    relays = relays if relays is not None else nodes

    # Eliminate contact with itself if it exists (needs to be done before adding -1 and -2)
    cp = cp.loc[~(cp.orig == cp.dest)]

    # Add dummy initial and final contacts: (orig, dest, tstart, tend, duration, range, rate, capacity)
    cp.loc[-1, :] = (orig, orig, t, t, 0.0, 0.0, np.inf, np.inf)
    cp.loc[-2, :] = (dest, dest, np.inf, np.inf, 0.0, 0.0, np.inf, np.inf)
    cp = cp.sort_values(['tstart', 'tend', 'orig', 'dest'])

    # Initialize necessary data structures
    cp['EAT']    = tinf
    cp['owlt']   = cp['range']
    cp['margin'] = ((1.0 * max_speed / 3600) * cp.owlt) / 186282
    cp.loc[-1, 'EAT'] = t

    # Transform to dict for fast processing. Format is {column -> [values]}
    idx = cp.index.values
    cp  = {c: cp[c].values for c in cp.columns}
    cp['index'] = idx

    # Initialize variables
    queue = []
    paths = []
    EATs = {}
    visited_nodes = {}
    found_paths = []

    # Start at the root contact
    queue.append(-1)
    paths.append((-1,))
    visited_nodes[(-1,)] = {orig}
    EATs[(-1,)] = t

    # While there are contacts to explore
    while queue:
        # Get the next contact
        cur_idx = queue.pop()
        c_idx   = cp['index'] == cur_idx
        c_dest  = np.compress(c_idx, cp['dest'])[0]  # Avoid fancy slow indexing
        path    = paths.pop()

        # Find path properties
        visited = visited_nodes[path]
        EAT     = EATs[path]

        # Get this contact neighbors. Neighbors meet the following criteria:
        # 1) The current.dest = contact.orig
        # 2) The contact.dest is a node that has already been visited
        # 3) The contact.tend > current.EAT (i.e. a neighboring contact does not end before data arrives to this contact)
        # 4) The neighbor contact's destination has relay capabilities or is the destination itself
        #    (note: this is not present in the SABR specification or ION code)
        cids = (c_dest == cp['orig']) & (~isin(cp['dest'], tuple(visited))) & (cp['tend'] > EAT) & \
               (isin(cp['dest'], list(relays)) | (cp['dest'] == dest))

        # If no neighbors identified, continue
        if not cids.any(): continue

        # Compute early transmission time (ETT) and early arrival time (EAT)
        ETT = np.maximum(np.compress(cids, cp['tstart']), EAT)
        EAT = ETT + np.compress(cids, cp['owlt']) + np.compress(cids, cp['margin'])

        # Iterate over neighbors
        for i, cid in enumerate(np.compress(cids, cp['index'])):
            # Create a record for this path
            p = list(deepcopy(path))
            p.append(cid)
            p = tuple(p)

            # If next neighbor is destination, save path
            if cid == -2:
                found_paths.append(p)
                if verbose: print('New path: ' + str(p))
                continue

            # Store neighbors EAT
            EATs[p] = EAT[i]
            visited_nodes[p] = visited | {c_dest} # Do not use ADD, it does not return anything

            # Append the neighbor to continue exploring the graph
            queue.append(cid)
            paths.append(p)

    # Initialize variables
    routes = []

    # Iterate over computed paths
    for path in found_paths:
        # Get the route (i.e. nodes traversed)
        path1 = path[1:]
        rt = tuple(np.compress(cp['index'] == idx, cp['orig'])[0] for idx in path1)

        # Get path contact list and EAT
        path2 = path[1:-1]
        end   = [np.compress(cp['index'] == idx, cp['tend'])[0] for idx in path2]
        ix    = np.argmin(end)

        # Compose route data structure
        route = {}
        route['orig'] = orig
        route['dest'] = dest
        route['time'] = t
        route['contacts'] = path2
        route['route'] = rt
        route['tstart'] = np.compress(cp['index'] == route['contacts'][0], cp['tstart'])[0]
        route['tend'] = end[ix]
        route['EAT']  = EATs[path[:-1]]
        route['limit_cid'] = path2[ix]
        route['nhops'] = len(rt)-1
        routes.append(route)

    return routes

# ============================================================================================================
# === VALIDATION: COMPARE SLOW AND FAST OUTPUTS
# ============================================================================================================

def validate_value(idx, v1, v2):
    if isinstance(v1, pd.Timestamp):
        eq = (v1 - v2).to_timedelta64() < np.timedelta64(1, 'ms')  # Precision of 1msec
    elif isinstance(v1, str_type):
        eq = v1 == v2
    elif isinstance(v1, Number):
        eq = np.isclose(v1, v2)
    elif isinstance(v1, (list, tuple)):
        eq = all(validate_value(idx, vv1, vv2) for vv1, vv2 in zip(v1, v2))
    else:
        raise ValueError('Cannot validate row {} of type {}'.format(idx, type(v1)))

    return eq

def validate_fast_cgr(cp, ri, t, orig, dest, relays, algorithm='bfs', ncpu=1):
    # Initialize variables
    diff = []

    # Load old route schedule
    disp('='*50 + ' COMPUTING ROUTE SCHEDULE - FAST MODE ' + '='*50)
    with Timer():
        slow_df = build_route_list(orig, dest, t, cp, ri, relays=relays, ncpu=ncpu, algorithm=algorithm, mode='fast')

    # Compute new route schedule
    disp('=' * 50 + ' COMPUTING ROUTE SCHEDULE - SLOW MODE ' + '=' * 50)
    with Timer():
        fast_df = build_route_list(orig, dest, t, cp, ri, relays=relays, ncpu=ncpu, algorithm=algorithm, mode='slow')
    
    # Compare rows
    disp('='*50 + ' VALIDATING ROUTE SCHEDULE - END ' + '='*50)
    for slow_cid, slow_row in slow_df.iterrows():
        # Get this row in the fast_df
        fast_row = fast_df.loc[slow_cid, :]        
        
        # Compare each entry of the row
        equal_idx = [validate_value(idx, slow_row[idx], slow_row[idx]) for idx in slow_row.index]

        # Flag non-equal entries
        diff_tags = slow_row.index[~np.array(equal_idx)].values
        if any(diff_tags):
            df = pd.concat((slow_row[diff_tags], fast_row[diff_tags]), axis=1)
            df.columns = ['Reference', 'New']
            diff.append(df)
            
    # If the fast_df has extra more rows than the slow_df, flag them
    slow_idx, fast_idx = set(slow_df.index), set(fast_df.index)
    for fast_cid in (fast_idx-slow_idx):
        diff.append(fast_df.loc[[fast_cid],:])
                
    return diff, fast_df, slow_df

if __name__ == '__main__':
    # Import for testing
    from . import build_route_list
    from simulator.utils.basic_utils import disp, read, Timer
    from numbers import Number
    from simulator.utils.time_utils import str2time

    # Load data
    contact_plan    = read('.\Scenario 2 - Data\Scn2_contact_table.xlsx')
    range_intervals = read('.\Scenario 2 - Data\Scn2_range_intervals.xlsx')
    
    # Define inputs
    t      = str2time('01-JAN-2034 00:00:00', fmt='%d-%b-%Y %H:%M:%S')
    nodes  = ('MR1','DSH','MCC','PSH','HHC','MMU','EVA1','EVA2','MOI','PDSR','PEV','PTX','EDL-MAV','EDL-DS')
    relays = ('PSH', 'DSH', 'MR1')

    # TEST 1 - Validate CGR fast implementation
    '''diff, fast_df, slow_df = validate_fast_cgr(contact_plan, range_intervals, t, nodes, nodes, relays, ncpu=5)
    if not diff: print('Fast CGR implementation successfully validated.')
    else: print('Error in CGR fast implementation, check:\n', diff)'''

    # TEST 2 - Build routes between two given nodes
    routes = build_route_list('MCC', 'PSH', t, contact_plan, range_intervals, relays=relays, ncpu=1,
                              algorithm='bfs', mode='slow', verbose=True)
    pd.DataFrame(routes).to_excel('routes 2.xlsx')

    
    