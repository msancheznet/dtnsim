import numpy as np

from simulator.routers.DtnCgrBasicRouter import DtnCgrBasicRouter

class NwcEcgrBasicRouter(DtnCgrBasicRouter):
    def find_best_route(self, orig, dest, bundle_size, visited, excluded):
        """ Implementation of the Dijkstra algorithm over the contact graph """
        # Get the contact plan. Reset variables
        cp = self.__class__._cp

        # Initialize variables
        cur_idx   = -1
        best_E    = np.inf
        final_cid = None

        # Reset the contact plan
        cp['EAT']         = np.full_like(cp['index'], np.inf, dtype='float')
        cp['energy']      = np.full_like(cp['index'], np.inf, dtype='float')
        cp['predecessor'] = np.full_like(cp['index'], -np.inf, dtype='float')

        # Set the -1 and -2 contacts to the origin and destination
        idx1, idx2 = cp['index'] == -1, cp['index'] == -2
        cp['orig'][idx1]   = orig
        cp['dest'][idx1]   = orig
        cp['EAT'][idx1]    = self.t
        cp['energy'][idx1] = 0.0
        cp['orig'][idx2]   = dest
        cp['dest'][idx2]   = dest

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
            c_EGY  = cp['energy'][c_idx][0]

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
                # Compute early transmission time (ETT) as the max between the contact
                # start, and the time at which the data arrives.
                ETT = np.maximum(cp['tstart'][cids], c_EAT)

                # Compute the total stored time (TST) that the data is stored in the node as difference
                # between the ETT and the time the data arrived
                TST = ETT - c_EAT

                # Compute the early arrival time (EAT) at the next node as the ETT plus the OWLT
                EAT = ETT + cp['owlt'][cids]

                # Compute energy consumed in this hop by this bundle.
                # NOTE: The transmission energy is estimated pessimistically at
                #       1J because bundle size is 1Mbit and min data rate is 1Mbps,
                #       so it would take 1 second the transmit the bundle.
                EGY = c_EGY + TST * self.env.nodes[c_dest].P_hotel + \
                                    self.env.nodes[c_dest].P_radio

                # Update the distance to candidate nodes if it is lower than
                # the distance that was already available
                cp['EAT'][cids]    = np.minimum(EAT, cp['EAT'][cids])
                cp['energy'][cids] = np.minimum(EGY, cp['energy'][cids])

                # POTENTIALLY CHANGE
                to_update = cids & np.in1d(cp['energy'], EGY)  # This is the performance bottleneck!!
                cp['predecessor'][to_update] = cur_idx

                # Check if any paths found up until this point get you to destination.
                # If so, they might be the best path to it.
                maybe_best = cids & (cp['dest'] == dest)

                # If so, save the best path found if better than previous paths
                if maybe_best.any():
                    # Get best EAT found in this iteration
                    maybe_best_idx = np.argmin(cp['energy'][maybe_best])       # This is a number (e.g. 0)
                    maybe_best_cid = cp['index'][maybe_best][maybe_best_idx]   # This is a number (e.g. cid=286)
                    maybe_best_E   = cp['energy'][maybe_best][maybe_best_idx]  # This is a number (e.g. EAT=1020)

                    # If the new found path is better than before, update the best found
                    # path
                    if maybe_best_E < best_E:
                        final_cid, best_E = maybe_best_cid, maybe_best_E

            # Find the next node to continue the Dijkstra search. It must satisfy:
            # 1) Contact that is valid (not suppressed, not towards node already visited or not a relay)
            # 2) Contact that is not the origin or destination
            # 3) Contact must have a path leading to it. Otherwise this a part of the graph not explored.
            # 4) Look for paths that can potentially improve the EAT. In other words, any path that has
            #    an EAT later than your currently best EAT, cannot improve the solution. Therefore, kill
            #    it (same idea as branch and cut)
            cids = valid_cids & (cp['index'] >= 0) & (cp['predecessor'] >= -1) & (cp['energy'] < best_E)

            # If not extra nodes to visit, you are done
            if not cids.any(): break

            # Continue search by exploring the node with lower EAT
            cur_idx = cp['index'][cids][np.argmin(cp['energy'][cids])]

        # If no path was found, return
        if final_cid is None: return None

        # Build the route and return
        return self.build_route(orig, dest, cp, final_cid)