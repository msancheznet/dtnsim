import numpy as np
from simulator.routers.DtnAbstractRouter import DtnAbstractRouter, RtRecord

class DtnCgrBasicRouter(DtnAbstractRouter):
    """ Class that implements a basic CGR router. No anchoring mechanism is provided,
        just the absolute best route is provided. No capacity calculations are provided
        either
    """
    # Variable to store the contact plan
    _cp = None
    _cl = None

    def reset(self):
        # Reset static variables
        self.__class__._cp = None
        self.__class__._cl = None

    def initialize(self):
        # Get the list of relays
        if self.props.relays == 'all':
            self.relays     = None
            self.non_relays = set(self.env.nodes.keys())
        else:
            self.relays     = self.props.relays
            self.non_relays = set(self.env.nodes.keys()) -  set(self.relays)

        # Get the mobility model for this router
        self.mobility_model = self.parent.mobility_model

        # Initialize contacts and ranges
        self.initialize_contacts_and_ranges()

    def initialize_contacts_and_ranges(self):
        # Working on static properties of the class, do it once only
        if self.__class__._cp is not None: return

        # Get the contacts and ranges from the contact
        cp = self.mobility_model.contacts_df.copy(deep=True)

        # Check that the contact plan was properly imported
        assert cp is not None, 'Contact plan is None'

        # Eliminate contact with itself if it exists (needs to be done before adding -1 and -2)
        cp = cp.loc[~(cp.orig == cp.dest)]

        # Add placeholders for initial and final contacts
        # (orig, dest, tstart, tend, duration, range, rate, capacity)
        cp.loc[-1, :] = ('', '', 0.0, np.inf, np.inf, 0.0, np.inf, np.inf)
        cp.loc[-2, :] = ('', '', 0.0, np.inf, np.inf, 0.0, np.inf, np.inf)
        Nr, _ = cp.shape

        # Transform to dict for fast processing. Format is {column -> [values]}
        idx         = cp.index.values
        cp          = {c: cp[c].values for c in cp.columns}
        cp['index'] = idx

        # Initialize variables
        cp['owlt']        = cp['range'] * (1 + 125 / 186000)  # Includes margin
        cp['EAT']         = np.inf * np.ones(Nr)
        cp['predecessor'] = -np.inf * np.ones(Nr)
        cp['suppressed']  = np.zeros(Nr, dtype='bool')

        # Mark the EAT for the initial contact
        cp['EAT'][idx == -1] = 0.0

        # Counter of capacity left in a contact
        self.cid_capacity = cp['capacity'].copy()

        # Save processed contact plan and contact list
        self.__class__._cp = cp
        self.__class__._cl = self.mobility_model.contacts_df.to_dict(orient='index')

    def find_routes(self, bundle, first_time, **kwargs):
        # Increase counter
        self.counter += 1

        # Get best route
        try:
            route = self.find_best_route(self.parent.nid, bundle.dest, bundle.data_vol,
                                         bundle.visited, bundle.excluded)
        except Exception as e:
            print(f'{self.parent.nid}: Exception in router')
            print(e)
            route = None

        # If not route was found, return
        if route is None: return None, None

        # Construct the routing record
        cid        = route['contacts'][0]
        con        = self.__class__._cl[cid]
        con['cid'] = cid
        rec = RtRecord(bundle=bundle, contact=con, route=route, priority=0, neighbor=con['dest'])

        # Subtract capacity from this cid
        cp  = self.__class__._cp
        cid = cp['index'] == cid
        cp['capacity'][cid] = np.maximum(0, cp['capacity'][cid]-bundle.data_vol)

        # Return record
        return [rec], []

    def find_best_route(self, orig, dest, bundle_size, visited, excluded):
        """ Implementation of the Dijkstra algorithm over the contact graph """
        # Get the contact plan. Reset variables
        cp = self.__class__._cp

        # Initialize variables
        cur_idx   = -1
        best_EAT  = np.inf
        final_cid = None

        # Reset the contact plan
        cp['EAT']         = np.full_like(cp['index'], np.inf, dtype='float')
        cp['predecessor'] = np.full_like(cp['index'], -np.inf, dtype='float')

        # Set the -1 and -2 contacts to the origin and destination
        idx1, idx2 = cp['index'] == -1, cp['index'] == -2
        cp['orig'][idx1] = orig
        cp['dest'][idx1] = orig
        cp['EAT'][idx1]  = self.t   # Before 0.0
        cp['orig'][idx2] = dest
        cp['dest'][idx2] = dest

        # List of valid contacts. Eliminate suppressed and contacts that have ended or don't have
        # enough capacity to accommodate this bundle.
        valid_cids = (~cp['suppressed']) & (cp['tend'] > self.t) & (cp['capacity'] >= bundle_size)

        # Eliminate all contacts going to nodes that have already been visited
        valid_cids &= ~np.in1d(cp['dest'], visited)

        # Eliminate all excluded contacts
        if excluded: valid_cids &= ~np.in1d(cp['index'], excluded)

        while self.is_alive:
            # Get information on current contact
            c_idx  = cp['index'] == cur_idx
            c_dest = cp['dest'][c_idx][0]
            c_EAT  = cp['EAT'][c_idx][0]

            # No contact to the current node can be valid any more since you don't want loops
            # in the computed route
            valid_cids[cp['dest'] == c_dest] = False

            # Get this contact neighbors. Neighbors meet the following criteria:
            # 1) The current.dest = contact.orig
            # 2) The contact is valid (not suppressed, not to node already visited, not to node not a relay)
            # 3) The current.EAT  < contact.tend (i.e. eliminate contacts that end before data arrives)
            cids = (c_dest == cp['orig']) & valid_cids & (cp['tend'] > c_EAT)

            # If you found new neighbors, process them
            if cids.any():
                # Compute early transmission time (ETT) and early arrival time (EAT)
                ETT = np.maximum(cp['tstart'][cids], c_EAT)
                EAT = ETT + cp['owlt'][cids]

                # Update the distance to candidate nodes if it is lower than
                # the distance that was already available
                cp['EAT'][cids] = np.minimum(EAT, cp['EAT'][cids])
                to_update = cids & np.in1d(cp['EAT'], EAT)              # This is the performance bottleneck!!
                cp['predecessor'][to_update] = cur_idx

                # Check if any paths found up until this point get you to destination.
                # If so, they might be the best path to it.
                maybe_best = cids & (cp['dest'] == dest)

                # If so, save the best path found if better than previous paths
                if maybe_best.any():
                    # Get best EAT found in this iteration
                    maybe_best_idx = np.argmin(cp['EAT'][maybe_best])         # This is a number (e.g. 0)
                    maybe_best_cid = cp['index'][maybe_best][maybe_best_idx]  # This is a number (e.g. cid=286)
                    maybe_best_EAT = cp['EAT'][maybe_best][maybe_best_idx]    # This is a number (e.g. EAT=1020)

                    # If the new found path is better than before, update the best found
                    # path
                    if maybe_best_EAT < best_EAT:
                        final_cid, best_EAT = maybe_best_cid, maybe_best_EAT

            # Find the next node to continue the Dijkstra search. It must satisfy:
            # 1) Contact that is valid (not suppressed, not towards node already visited or not a relay)
            # 2) Contact that is not the origin or destination
            # 3) Contact must have a path leading to it. Otherwise this a part of the graph not explored.
            # 4) Look for paths that can potentially improve the EAT. In other words, any path that has
            #    an EAT later than your currently best EAT, cannot improve the solution. Therefore, kill
            #    it (same idea as branch and cut)
            cids = valid_cids & (cp['index'] >= 0) & (cp['predecessor'] >= -1) & (cp['EAT'] < best_EAT)

            # If not extra nodes to visit, you are done
            if not cids.any(): break

            # Continue search by exploring the node with lower EAT
            cur_idx = cp['index'][cids][np.argmin(cp['EAT'][cids])]

        # If no path was found, return
        if final_cid is None: return None

        # Build the route and return
        return self.build_route(orig, dest, cp, final_cid, EAT=best_EAT)

    def build_route(self, orig, dest, cp, final_cid, EAT=-1):
        # Initialize variables
        contacts, rt = [], []
        cur_idx = final_cid
        early_end = np.inf
        limit_cid = np.inf

        # Compute properties about this route:
        # 1) Contacts for this route
        # 2) Early end = Time at which the route is not usable because one of its contacts ends
        while not cur_idx == -1:
            # Get contact information
            c_idx  = cp['index'] == cur_idx
            c_name = cp['index'][c_idx][0]
            c_dest = cp['dest'][c_idx][0]
            c_tend = cp['tend'][c_idx][0]
            c_predecessor = cp['predecessor'][c_idx][0]

            # If this contact ends before any other, it is the limiting contact
            if c_tend < early_end: early_end, limit_cid = c_tend, cur_idx

            # Save contacts and route
            contacts.append(c_name)
            rt.append(c_dest)

            # Continue backtracking
            cur_idx = c_predecessor

        # Add the origin as the first contact
        rt.append(orig)

        # Reverse contact list and route
        rt, cts = tuple(reversed(rt)), tuple(reversed(contacts))

        # If the best_EAT is not provided, then you have to compute it
        if EAT == -1:
            for cid in cts:
                idx = cp['index'] == cid
                ETT = np.maximum(cp['tstart'][idx][0], EAT)
                EAT = ETT + cp['owlt'][idx][0]

        # Return route as dictionary
        return {'orig': orig, 'dest': dest, 'contacts': cts, 'route': rt,
                'tstart': cp['tstart'][cp['index'] == cts[0]][0],
                'tend': early_end, 'EAT': EAT, 'limit_cid': limit_cid,
                'nhops': len(cts)}