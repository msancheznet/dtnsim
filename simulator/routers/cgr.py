import numpy as np
import pandas as pd
from .utils import isin, str_type

# ============================================================================================================
# === BUILD A COLLECTION OF ROUTES BETWEEN ONE ORIG AND DEST
# ============================================================================================================

def cgr_build_route_list_fast(orig, dest, t, contact_plan, relays=None, max_speed=125, verbose=False):
    """ Implement the Dijkstra algorithm to find the route that delivers data the earliest

        :param orig: Name of the node where the bundle originates (e.g. PSH)
        :param dest: Name of the node where the bundle is destined for (e.g. Earth)
        :param pandas.Timestamp t: Time at which the bundle needs to be routed
        :param pandas.DataFrame contact_plan: Contact table
        :param tuple relays: Name of the nodes that can be used as relays to construct the route. Default is None, which
                             indicates that all nodes can be relays
        :param float max_speed: Max speed that a spacecraft can move in mph. Default is 125 miles/sec
        :return list: List of routes. See ``find_route`` to see the information in a route
    """
    # Initialize variables
    routes = []
    anchor = None
    cp     = contact_plan.copy(deep=True)
    tinf   = max(cp.tstart.max(), cp.tend.max()) + 100 * 365 * 24 * 3600
    nodes  = set(cp.orig).union(set(cp.dest))
    relays = list(relays) if relays is not None else list(nodes)
    count  = 0
    msg    = 'Route {}-{}: [{}]\tEAT={}, Validity=({}, {}), Contacts={}, Hops={}'
    r_cids = set()

    # Eliminate contact with itself if it exists (needs to be done before adding -1 and -2)
    cp = cp.loc[~(cp.orig==cp.dest)]

    # Add dummy initial and final contacts (orig, dest, tstart, tend, rate, duration, range, rate, capacity)
    cp.loc[-1, :] = (orig, orig, t, t, 0.0, 0.0, np.inf, np.inf)
    cp.loc[-2, :] = (dest, dest, tinf, tinf, 0.0, 0.0, np.inf, np.inf)
    cp = cp.sort_values(['tstart', 'tend', 'orig', 'dest'])
    Nrows, Ncols = cp.shape

    # Transform to dict for fast processing. Format is {column -> [values]}
    idx = cp.index.values
    cp  = {c: cp[c].values for c in cp.columns}
    cp['index'] = idx

    # Initialize variables
    cp['owlt']   = cp['range']
    cp['margin'] = cp['owlt']*(1+max_speed/186000)
    cp['EAT']    = np.array([tinf]*Nrows)
    cp['predecessor'] = np.array([None] * Nrows)
    cp['visited']     = np.array([False] * Nrows)
    cp['suppressed']  = np.array([False] * Nrows)

    # Mark the EAT for the initial contact
    cp['EAT'][idx == -1] = t

    while True:
        # Use dijkstra algorithm to find a route
        route = find_route_fast(orig, dest, cp, tinf, relays)

        # No more routes are available, exit
        if route is None:  break

        # Fill out constant route properties
        route['orig'] = orig
        route['time'] = t

        # Initialize variables
        first_contact = route['contacts'][0]

        # If anchor available, use if
        if anchor is not None and first_contact != anchor:
            # End anchored route search
            cp['suppressed'][cp['orig'] != orig]    = False
            cp['suppressed'][cp['index'] == anchor] = True
            anchor = None
        else:
            # Store computed route
            routes.append(route)

            # Log the addition of the route. Note that this has to be done here since if anchor is not None,
            # the resulting route might get invalidated
            if verbose is True:
                disp(msg.format(orig, dest, count, route['EAT'], route['tstart'], route['tend'], route['contacts'], route['route']))
                count += 1

            # Add this combination of contacts to the r_cids set. If already present show error
            if route['contacts'] in r_cids:         
                warn('A route from {} to {} with contacts {} already exists. This one is discarded', orig, dest, route['contacts'])
                continue
            else: r_cids.add(route['contacts'])

            # Select the anchor and suppress it to get a new route
            limit_contact = route['limit_cid']
            cp['suppressed'][cp['index'] == limit_contact] = True

            # Set the anchor contact if necessary
            if limit_contact != first_contact:
                anchor = first_contact

        # Reset data for find_route (dijkstra)
        cp['EAT'][cp['index']>=0]  = tinf
        cp['predecessor']          = np.array([None]*Nrows)
        cp['visited']              = np.array([False]*Nrows)

    return routes

def cgr_build_route_list_slow(orig, dest, t, contact_plan, relays=None, max_speed=125, verbose=False):
    """ Implement the Dijkstra algorithm to find the route that delivers data the earliest

        :param orig: Name of the node where the bundle originates (e.g. PSH)
        :param dest: Name of the node where the bundle is destined for (e.g. Earth)
        :param pandas.Timestamp t: Time at which the bundle needs to be routed
        :param pandas.DataFrame contact_plan: Contact table
        :param pandas.DataFrame range_intervals: Table with range intervals
        :param tuple relays: Name of the nodes that can be used as relays to construct the route. Default is None, which
                             indicates that all nodes can be relays
        :param float max_speed: Max speed that a spacecraft can move in mph. Default is 125 miles/sec
        :return list: List of routes. See ``find_route`` to see the information in a route
    """
    # Initialize variables
    routes = []
    anchor = None
    cp     = contact_plan.copy(deep=True)
    tinf   = max(cp.tstart.max(), cp.tend.max()) + 100*365*24*3600
    nodes  = set(cp.orig).union(set(cp.dest))
    relays = relays if relays is not None else nodes
    count  = 0
    msg    = 'Route {}-{}: [{}]\tEAT={}, Validity=({}, {}), Contacts={}, Hops={}'
    r_cids = set()

    # Eliminate contact with itself if it exists (needs to be done before adding -1 and -2)
    cp = cp.loc[~(cp.orig==cp.dest)]

    # Add dummy initial and final contacts: (orig, dest, tstart, tend, duration, range, rate, capacity)
    cp.loc[-1, :] = (orig, orig, t, t, t - t, 0.0, np.inf, np.inf)
    cp.loc[-2, :] = (dest, dest, np.inf, np.inf, t - t, 0.0, np.inf, np.inf)
    cp = cp.sort_values(['tstart', 'tend', 'orig', 'dest'])

    # Initialize necessary data structures
    cp['EAT']         = tinf
    cp['owlt']        = cp['range']
    cp['margin']      = cp.owlt*(1+max_speed/186000)
    cp['predecessor'] = None
    cp['visited']     = False
    cp['suppressed']  = False
    cp.loc[-1, 'EAT'] = t

    while True:
        # Use dijkstra algorithm to find a route
        route = find_route_slow(orig, dest, cp, tinf, relays)

        # No more routes are available, exit
        if route is None: break

        # Fill out constant route properties
        route['orig'] = orig
        route['time'] = t

        # Initialize variables
        first_contact = route['contacts'][0]

        # If anchor available, use if
        if anchor is not None:
            if anchor != first_contact:
                cp.loc[cp.index >= 0, 'EAT'] = tinf
                cp['predecessor'] = None
                cp['visited'] = False

                cp.loc[cp.orig != orig, 'suppressed'] = False
                cp.loc[anchor, 'suppressed'] = True
                anchor = None
                continue

        # Store computed route
        routes.append(route)

        # Log the addition of the route. Note that this has to be done here since if anchor is not None,
        # the resulting route might get invalidated
        if verbose is True:
            disp(msg.format(orig, dest, count, route['EAT'], route['tstart'], route['tend'], route['contacts'],
                            route['route']))
            count += 1

        # Add this combination of contacts to the r_cids set. If already present show error
        if route['contacts'] in r_cids:
            warn('A route from {} to {} with contacts {} already exists. This one is discarded', orig, dest,
                 route['contacts'])
            continue
        else:
            r_cids.add(route['contacts'])

        # Select the anchor and suppress it to get a new route
        limit_contact = route['limit_cid']
        if limit_contact != first_contact: anchor = first_contact
        cp.loc[limit_contact, 'suppressed'] = True

        # Reset data for find_route (dijkstra)
        cp.loc[cp.index>=0, 'EAT'] = tinf
        cp['predecessor']          = None
        cp['visited']              = False

    return routes

# ============================================================================================================
# === FIND ONE ROUTE BETWEEN ONE ORIG AND DEST
# ============================================================================================================

def find_route_fast(orig, dest, cp, tinf, relays, root=-1):
    """ Implement the Dijkstra algorithm to find the route that delivers data earlier

        .. Tip:: Dijkstra does not need the full tree to be built prior to its application. Therefore,
                 the input is just the contact table and the graph is built incrementally

        .. Tip:: To see a basic implementation of the Dijkstra algorithm in python see `here <https://stackoverflow.com/questions/22897209/dijkstras-algorithm-in-python>`_
                 This implementation, however, takes advantage of pandas indexing mechanism to eliminate the need for any ``for`` loops inside the main ``while`` loop.

        :param orig: Name of the node where the bundle originates (e.g. PSH)
        :param dest: Name of the node where the bundle is destined for (e.g. Earth)
        :param pandas.DataFrame cp: Copy of the contact table that will be modified during the Dijkstra search
        :param pandas.Timestamp tinf: Timestamp that denotes infinity (by default, 10 years after any event in the contact plan table)
        :param tuple relays: Names for all nodes that can be used as relays to construct routes
        :param int root: Id of the root note (by default -1)
        :return dict: A dictionary with the best route
    """
    # Check inputs
    assert orig != dest, 'Trying to find a round between the same node {}. This will make this function crash!'.format(orig)

    # Initialize variables
    route         = {}
    cur_idx       = root
    best_EAT      = tinf
    final_contact = None
    visited_nodes = []

    while True:
        # Get information on current contact
        c_idx  = cp['index'] == cur_idx
        c_dest = np.compress(c_idx, cp['dest'])     # Avoid fancy slow indexing
        c_EAT  = np.compress(c_idx, cp['EAT'])      # Avoid fancy slow indexing

        # Get this contact neighbours. Neighbours meet the following criteria:
        # 1) The current.dest = contact.orig
        # 2) The contact.dest is a node that has already been visited
        # 3) The current.EAT  < contact.tend (i.e. eliminate contacts that end before data arrives)
        # 4) They are not suppressed or already visited
        # 5) The neighbor contact's destination has relay capabilities or is the destination itself
        #    (note: this is not present in the SABR specification or ION code)
        cids = (c_dest == cp['orig']) & (~isin(cp['dest'], visited_nodes)) & (isin(cp['dest'], relays) | (cp['dest'] == dest)) & \
               (cp['tend'] > c_EAT) & (cp['suppressed'] == False) & (cp['visited'] == False)
        if cids.any() == True:
            # Compute early transmission time (ETT) and early arrival time (EAT)
            ETT = np.maximum(cp['tstart'][cids], c_EAT)
            EAT = ETT + cp['owlt'][cids] + cp['margin'][cids]

            # Update the distance to candidate nodes if it is lower than
            # the distance that was already available
            cp['EAT'][cids] = np.minimum(EAT, cp['EAT'][cids])
            to_update = cids & (np.sum([cp['EAT'] == t for t in EAT], axis=0) != 0)
            cp['predecessor'][to_update] = cur_idx

            # Store the best path found to the final node
            test = cids & (cp['dest'] == dest)
            candidates, idx = cp['EAT'][test], cp['index'][test]
            if candidates.size != 0:
                candidate_best_idx = np.take(idx, np.argmin(candidates), axis=0)
                candidate_best     = cp['index'] == candidate_best_idx
                if cp['EAT'][candidate_best] < best_EAT:
                    final_contact, best_EAT = candidate_best_idx, cp['EAT'][candidate_best][0]

        # Mark the current contact as explored
        cp['visited'][cp['index'] == cur_idx] = True

        # To continue search, you need a node that has not been suppressed or visited,
        # it is not the origin or destination, and you have found a path to it.
        cids = (cp['index'] >= 0) & (cp['suppressed'] == False) & (cp['visited'] == False) & \
               (cp['EAT'] < best_EAT) & (~pd.isnull(cp['predecessor']))
        if cids.any() == False:
            break

        # Continue search
        cur_idx = np.take(cp['index'][cids], np.argmin(cp['EAT'][cids]), axis=0)

        # Reconstruct the path from this contact. Figure out which nodes have been visited
        # so that you do not visit them again. This solves the problem of routes like N1->N2->N1->N3
        visited_nodes, idx = [], cur_idx
        while idx != -1:
            c_idx = cp['index'] == idx
            visited_nodes.append(np.compress(c_idx, cp['dest'])[0])
            idx = np.compress(c_idx, cp['predecessor'])
        visited_nodes.append(np.compress(cp['index'] == -1, cp['dest'])[0])

    # Compute properties about this route:
    # 1) Contacts for this route
    # 2) Early end = Time at which the route is not usable because one of its contacts ends
    # 3) Max. capacity = min(capacity for its contacts)
    if final_contact is not None:
        contacts, rt = [], []
        early_end, limit_contact = tinf, np.inf
        cur_idx   = final_contact
        while not cur_idx == root:
            # Get contact information
            c_idx         = cp['index'] == cur_idx
            c_name        = np.compress(c_idx, cp['index'])[0]
            c_dest        = np.compress(c_idx, cp['dest'])[0]
            c_tend        = np.compress(c_idx, cp['tend'])[0]
            c_predecessor = np.compress(c_idx, cp['predecessor'])[0]

            # Reconstruct route
            if c_tend < early_end:
                early_end     = c_tend
                limit_contact = cur_idx
            contacts.append(c_name)
            rt.append(c_dest)
            cur_idx   = c_predecessor
        rt.append(orig)

        # Return route as dictionary
        route['orig']      = orig
        route['dest']      = dest
        route['contacts']  = tuple(reversed(contacts))
        route['route']     = tuple(reversed(rt))
        route['tstart']    = cp['tstart'][cp['index'] == route['contacts'][0]][0]
        route['tend']      = early_end
        route['EAT']       = best_EAT
        route['limit_cid'] = limit_contact
        route['nhops']    = len(route['contacts'])
        return route

    # If you reached this point, then search has ended, no route could be found
    return None

def find_route_slow(orig, dest, cp, tinf, relays, root=-1):
    """ Implement the Dijkstra algorithm to find the route that delivers data earlier

        .. Tip:: Dijkstra does not need the full tree to be built prior to its application. Therefore,
                 the input is just the contact table and the graph is built incrementally

        .. Tip:: To see a basic implementation of the Dijkstra algorithm in python see `here <https://stackoverflow.com/questions/22897209/dijkstras-algorithm-in-python>`_
                 This implementation, however, takes advantage of pandas indexing mechanism to eliminate the need for any ``for`` loops inside the main ``while`` loop.

        :param orig: Name of the node where the bundle originates (e.g. PSH)
        :param dest: Name of the node where the bundle is destined for (e.g. Earth)
        :param pandas.DataFrame cp: Copy of the contact table that will be modified during the Dijkstra search
        :param pandas.DataFrame ri: Copy of the range intervals table that will be modified during the Dijkstra serch
        :param pandas.Timestamp tinf: Timestamp that denotes infinity (by default, 10 years after any event in the contact plan table)
        :param tuple relays: Names for all nodes that can be used as relays to construct routes
        :param int root: Id of the root note (by default -1)
        :return dict: A dictionary with the best route
    """
    # Initialize variables
    route         = {}
    cur_idx       = root
    best_EAT      = tinf
    final_contact = None
    visited_nodes = []

    while True:
        # Get A COPY of current contact
        current = cp.loc[cur_idx, :]

        # Get this contact neighbors. Neighbors meet the following criteria:
        # 1) The current.dest = contact.orig
        # 2) The contact.dest is a node that has already been visited
        # 3) The current.EAT  < contact.tend (i.e. eliminate contacts that end before data arrives)
        # 4) They are not suppressed or already visited
        # 5) The neighbor contact's destination has relay capabilities or is the destination itself
        #    (note: this is not present in the SABR specification or ION code)
        cids = (current.dest == cp.orig) & (~cp.dest.isin(visited_nodes)) & (cp.dest.isin(relays) | (cp.dest == dest)) & \
               (cp.tend > current.EAT) & (cp.suppressed == False) & (cp.visited == False)
        if any(cids) is True:
            # Compute early transmission time (ETT) and early arrival time (EAT)
            ETT = cp.tstart[cids].apply(lambda x: max(x, current.EAT))
            EAT = ETT + cp.owlt[cids] + cp.margin[cids]

            # Update the distance to candidate nodes if it is lower than
            # the distance that was already available
            cp.loc[cids, 'EAT'] = np.minimum(EAT, cp.EAT[cids])
            cp.loc[cids & (cp.EAT[cids] == EAT), 'predecessor'] = cur_idx

            # Store the best path found to the final node
            candidates = cp.EAT[cids & (cp.dest == dest)]
            if any(candidates):
                candidate_best = candidates.idxmin()
                if cp.EAT[candidate_best] < best_EAT:
                    final_contact, best_EAT = candidate_best, cp.EAT[candidate_best]

        # Mark the current contact as explored
        cp.loc[cur_idx, 'visited'] = True

        # To continue search, you need a node that has not been suppressed or visited,
        # it is not the origin or destination, and you have found a path to it.
        cids = (cp.index >= 0) & (cp.suppressed == False) & (cp.visited == False) & \
               (cp.EAT < best_EAT) & (~pd.isnull(cp.predecessor))
        if any(cids) is False:
            break

        # Continue search
        cur_idx = cp.EAT[cids].idxmin()

        # Reconstruct the path from this contact. Figure out which nodes have been visited
        # so that you do not visit them again. This solves the problem of routes like N1->N2->N1->N3
        visited_nodes, idx = [], cur_idx
        while idx != -1:
            visited_nodes.append(cp.dest[idx])
            idx = cp.predecessor[idx]
        visited_nodes.append(cp.dest[idx])

    # Compute properties about this route:
    # 1) Contacts for this route
    # 2) Early end = Time at which the route is not usable because one of its contacts ends
    if final_contact is not None:
        contacts, rt = [], []
        early_end, limit_contact = tinf, np.inf
        cur_idx   = final_contact
        while not cur_idx == root:
            contact   = cp.loc[cur_idx, :]
            if contact.tend < early_end:
                early_end     = contact.tend
                limit_contact = cur_idx
            contacts.append(contact.name)
            rt.append(contact.dest)
            cur_idx   = contact.predecessor
        rt.append(orig)

        # Return route as dictionary
        route['orig']      = orig
        route['dest']      = dest
        route['contacts']  = tuple(reversed(contacts))
        route['route']     = tuple(reversed(rt))
        route['tstart']    = cp.loc[route['contacts'][0], 'tstart']
        route['tend']      = early_end
        route['EAT']       = best_EAT
        route['limit_cid'] = limit_contact
        route['nhops']    = len(route['contacts'])
        return route

    # If you reached this point, then search has ended, no route could be found
    return None

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
    from simulator.utils.basic_utils import disp, read, Timer, warn
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

    
    