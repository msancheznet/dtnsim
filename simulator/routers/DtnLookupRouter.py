import numpy as np
import pandas as pd
from simulator.utils.DtnIO import load_route_schedule_file
from simulator.routers import build_route_list
from simulator.routers.DtnAbstractRouter import DtnAbstractRouter, RtRecord

class DtnLookupRouter(DtnAbstractRouter):
    """ Class that implements a router that looks up the route to use based on a
         pre-computed route schedule. This route schedule is provided as an excel
         file typically and can be computed using different methods (BFS, CGR+anchoring,
         CGR+Yen K, etc.)
    """
    _contacts_df = None         # Dataframe
    _ranges_df   = None         # Dataframe

    _all_routes   = None        # Dictionary
    _all_contacts = None        # Dictionary indexed by contact id
    _all_ranges   = None        # Dictionary indexed by contact id

    def __init__(self, env, parent):
        super().__init__(env, parent)
        # Initialize variables
        indir = self.config['globals'].indir
        self.routes_file  = indir / self.props.routes
        self.max_crit     = self.props.max_crit

    def reset(self):
        # Reset static variables
        self.__class__._contacts_df  = None
        self.__class__._ranges_df    = None
        self.__class__._all_routes   = None
        self.__class__._all_contacts = None
        self.__class__._all_ranges   = None

    def initialize(self):
        # Get list of relays
        self.relays = set(self.env.nodes.keys()) if self.props.relays == 'all' else self.props.relays
        self.non_relays = set(self.env.nodes.keys()) - self.relays

        # Get the mobility model for this router
        self.mobility_model = self.env.mobility_models[self.parent.props.mobility_model]

        # Initialize contacts and ranges
        self.initialize_contacts_and_ranges()

        # Initialize routes
        self.initialize_routes()

    def initialize_contacts_and_ranges(self):
        # Working on static properties of the class, do it once only
        if self.__class__._all_contacts is not None: return

        # Get the contacts and ranges from the contact
        cp = self.mobility_model.contacts_df
        ri = self.mobility_model.ranges_df

        # Check that the contact plan was properly imported
        assert cp is not None, 'Contact plan is None'
        assert ri is not None, 'Range intervals is None'

        # Store contacts and ranges df
        self.__class__._contacts_df = cp
        self.__class__._ranges_df   = ri

        # Depack dataframe to a dictionary to improve performance.
        self.__class__._all_contacts = cp.to_dict(orient='index')
        self.__class__._all_ranges   = ri.to_dict(orient='index')

    def initialize_routes(self):
        # Working on static properties of the class, do it once only
        if self.__class__._all_routes is not None: return

        # If routes file is provided, and re-computation is not forced, just load the file
        if self.props.routes != None and self.props.recompute_routes == False:
            print('Loading route schedule')
            routes = load_route_schedule_file(self.routes_file, self.epoch)
        else:
            routes = self.build_route_schedule(self.env.do_track)

        # Validate the route schedule
        routes = self.validate_route_list(routes)

        # Save route schedule if necessary
        if self.props.recompute_routes:
            path = self.config['globals'].indir / self.props.routes
            routes.to_excel(path)

        # If mode is slow, run translation mechanism
        routes = self.prepare_route_list(routes)

        # Store the routes
        self.__class__._all_routes = routes

    def find_routes(self, bundle, first_time, **kwargs):
        """ Find a route for a bundle. This is comprised of four steps:

            1) Building a route list
            2) Down-selecting the route list to find the best option for each neighbor
            3) Selecting the neighbor(s) depending on criticality
            4) Try the route to make sure that you will not miss any future contacts given the
               current time and backlog for this neighbor. If so, try a re-routers event
        """
        # Increase counter
        self.counter += 1

        # Step 1) Get route list
        try:
            options = self.build_route_list(bundle)
        except Exception as e:
            raise type(e)('t={}: Error creating route list for bundle {}.'.format(self.t, bundle))

        # If no options found, then tell the DtnNode forward function to drop this bundle
        # In reality, in ION you would probably check for alternate routing procedures
        if not options: return None, None

        # Step 2) Find proximate node list in the form of CgrRecord list
        try:
            rt_records = self.find_prox_node_list(bundle, options)
        except Exception as e:
            raise type(e)('t={}: Error creating proximate node list for bundle {}.'.format(self.t, bundle))

        # The proximate node list is empty. Return ([],[]), which will mark this bundle as dropped
        if not rt_records: return [], []

        # Step 3) Find next hop based on proximate node list
        if bundle.critical == True and first_time == True:
            next = self.select_neighbor_critical_bundle(rt_records)
        else:
            next = self.select_neighbor_standard_bundle(rt_records)

        # Step 4) Try the selected routes to see if they actually works.
        # NOTE: returns empty lists
        try:
            to_keep, cids_to_exclude = self.try_route_list(next)
        except Exception as e:
            raise type(e)('t={}: Error trying routes for bundle {}.'.format(self.t, bundle))

        # Return routes
        return to_keep, cids_to_exclude

    def build_route_list(self, bundle):
        # If the route schedule is available, use it
        if self.__class__._all_routes:
            try: return self.__class__._all_routes[self.parent.nid, bundle.dest]
            except KeyError: return

        # If the route schedule is not available, trigger cgr
        routes = build_route_list(self.parent.nid, bundle.dest, self.t, self._contacts_df, self._ranges_df,
                                  relays=self.relays, max_speed=self.props.max_speed,
                                  verbose=False, ncpu=1, algorithm=self.props.algorithm,
                                  mode=self.props.mode)

        # Validate the route list generated
        routes = self.validate_route_list(routes)

        # If mode is slow, run translation mechanism
        routes = self.prepare_route_list(routes)

        # Return the route list
        return routes[self.parent.nid, bundle.dest]

    def build_route_schedule(self, verbose=False):
        # Create the route schedule
        nodes  = list(self.env.nodes.keys())
        routes = build_route_list(nodes, nodes, 0.0, self._contacts_df, self._ranges_df, relays=self.relays,
                                  ncpu=self.props.num_cores, algorithm=self.props.algorithm,
                                  mode=self.props.mode, verbose=verbose)

        # Return the route schedule
        return routes

    def validate_route_list(self, routes):
        # Initialize variables
        to_keep  = []
        excluded = [','.join(r) for r in self.props.excluded_routes]

        # Filter routes that are invalid
        for idx, row in routes.iterrows():
            # Initialize variables
            route = row.route

            # Get the mid hops
            mid_hops = set(route[1:-1])

            # If the there is a non-relay in the mid hops, skip
            if not mid_hops.isdisjoint(self.non_relays): continue

            # If neither the tx and rx are relays, compute the number of hops
            if row.orig not in self.relays and row.dest not in self.relays:
                # Compute the number of hops through a relay.
                relay_hops = np.in1d(list(self.relays), route).sum()

                # If too many relay hops, continue
                if relay_hops > self.props.max_relay_hops: continue

            # If this route contains any of the excluded routes, eliminate it
            route = ','.join(route)
            if any(exc in route for exc in excluded):
                continue

            to_keep.append(idx)

        # Filter routes that are valid
        routes = routes.loc[to_keep, :].reset_index(drop=True)

        return routes

    def prepare_route_list(self, routes):
        # If routes has already been prepared, return
        if isinstance(routes, dict): return routes

        # Initialize variables
        prepared_routes = {}
        routes          = {c: routes[c].values for c in routes.columns}    # {column -> [values]}
        contacts        = self.__class__._all_contacts

        # Process route schedule
        for o, d in pd.unique(list(zip(routes['orig'], routes['dest']))):
            # Get the indices for this o-d pair
            idx = (routes['orig'] == o) & (routes['dest'] == d)

            # Construct the data structure
            data = {}
            data['EAT']      = routes['EAT'][idx]
            data['nhops']    = routes['nhops'][idx].astype('int32')
            data['tstart']   = routes['tstart'][idx]
            data['tend']     = routes['tend'][idx]
            data['route']    = routes['route'][idx]
            data['contacts'] = routes['contacts'][idx]
            data['contacts_set'] = [set(c) for c in data['contacts']]
            data['nodes']    = [set(r) for r in data['route']]     # Full list of nodes visited, including origin
            data['hops']     = [r - {o} for r in data['nodes']]     # List of nodes visited, without the origin
            data['next_hop'] = np.array([r[1] for r in data['route']])
            data['next_cid'] = np.array([r[0] for r in data['contacts']])
            data['capacity'] = [min(contacts[cid]['capacity'] for cid in cts) for cts in data['contacts']]
            data['capacity'] = np.array(data['capacity'], dtype='float64')

            # Store the routes for this o-d pair
            prepared_routes[o, d] = data

        return prepared_routes

    def find_prox_node_list(self, bundle, opts):
        """ Find all neighbors to send the bundle to. Create a CgrRecord for each option
            Performs step 2 of ``find_routes``.
        """
        # Filter routes that end before now
        idx = opts['tend'] > self.t

        # Filter routes that go through already visited nodes
        if bundle.visited:
            tmp = set(bundle.visited)
            idx &= np.array([n.isdisjoint(tmp) for n in opts['hops']])

        # Filter routes that go through excluded contacts
        #if bundle.excluded: idx &= ~np.isin(opts['next_cid'], bundle.excluded)
        if bundle.excluded:
            tmp = set(bundle.excluded)
            idx &= np.array([c.isdisjoint(tmp) for c in opts['contacts_set']])

        # Filter routes that do not have enough capacity for this bundle
        idx &= (opts['capacity'] >= bundle.data_vol)

        # If all opts have been invalidated, return None
        if not idx.any(): return

        # Initialize variables
        candidates   = opts['next_hop'][idx]
        next_cids    = opts['next_cid'][idx]
        contacts     = opts['contacts'][idx]
        tstart_route = opts['tstart'][idx]
        tend_route   = opts['tend'][idx]
        rt_records = []

        # Figure out the priority of this bundle (0=critical, 1=false)
        priority = self.find_bundle_priority(bundle)

        # Get first contact for each neighbor. This relies on the fact that data
        # comes in sorted format
        while candidates.size > 0:
            idx = candidates == candidates[0]
            next_cid = next_cids[idx][0]
            contact  = contacts[idx][0]
            ts_route = tstart_route[idx][0]
            te_route = tend_route[idx][0]

            # Compose the DTN record and store it
            con = self.__class__._all_contacts[next_cid]
            con['cid'] = next_cid
            rte = {'tstart': ts_route, 'tend': te_route, 'contacts': contact}
            rec = RtRecord(bundle=bundle, contact=con, route=rte, priority=priority, neighbor=con['dest'])
            rt_records.append(rec)

            # Check if this routing decision has affected the current route
            if hasattr(bundle, 'cur_route'):
               if bundle.cur_route !=  contacts:
                   print('Route changed')

            # Eliminate all routes to the node already used
            candidates   = candidates[~idx]
            next_cids    = next_cids[~idx]
            contacts     = contacts[~idx]
            tstart_route = tstart_route[~idx]
            tend_route   = tend_route[~idx]

        return rt_records

    def select_neighbor_critical_bundle(self, rt_records):
        """ Select the next neighbors to send a critical bundle to.
            Performs step 3 of ``find_routes``.
        """
        return rt_records[:self.max_crit] if self.max_crit is not None else rt_records

    def select_neighbor_standard_bundle(self, rt_records):
        """ Select the next neighbor to send a standard bundle to.
            Performs step 3 of ``find_routes``.
        """
        return [rt_records[0]]

    def try_route_list(self, rt_records):
        # Initialize variables
        to_keep         = []
        cids_to_exclude = []
        EAT             = self.t

        # Iterate over route options
        for record in rt_records:
            # Initialize variables
            valid   = True
            bundle  = record.bundle
            contact = record.contact
            mngr    = self.parent.queues[contact['dest']]

            # Compute backlog for this neighbor
            if contact['cid'] == mngr.current_cid:
                backlog = mngr.queue.backlog  # [bits]
            else:
                backlog = mngr.future_backlog[contact['cid']]

            # Follow the route to see if you will miss any connections
            for cid in record.route['contacts']:
                # Get hop data
                dr = self.__class__._all_contacts[cid]['rate']  # [bps]
                Tp = self.__class__._all_contacts[cid]['range'] # [s]
                Te = self.__class__._all_contacts[cid]['tend']  # [s]

                # Compute the "Estimated Departure Time"
                EDT = max(EAT, contact['tstart']) + backlog/dr

                # Compute the "Estimated Arrival Time"
                EAT = EDT + bundle.data_vol/dr + Tp

                # If the estimated arrival time is too late, then this route is
                # not valid
                if EAT >= Te: valid = False; cids_to_exclude.append(cid); break

                # After the first hop you do not have information about the state
                # of another node's queues. Therefore, assume it is zero
                backlog = 0

            # If the route is valid, keep it
            if valid: to_keep.append(record)

        return to_keep, cids_to_exclude