#########################################################################################
# Copyright 2019, by the California Institute of Technology. ALL RIGHTS RESERVED.       #
# United States Government Sponsorship acknowledged.                                    #
# Any commercial use must be negotiated with the Office of Technology Transfer at the   #
# California Institute of Technology.                                                   #
#                                                                                       #
# This software may be subject to U.S. export control laws. By accepting this software, #
# the user agrees to comply with all applicable U.S. export laws and regulations. User  #
# has the responsibility to obtain export licenses, or other export authority as may be #
# required before exporting such information to foreign countries or providing access   #
# to foreign persons.                                                                   #
#########################################################################################

import sys
import networkx as nx
import copy
import numpy as np


def find_route_static_graph(bundle_size=None, contact_plan=None, current_time=0,
                                nodes_state=None, source=None, target=None,
                                preferred_path=None):
    # Initialize variables
    nodes = set()
    conns = {}

    # Find current network topology
    for c in contact_plan:
        if current_time > c['time_end'] or current_time < c['time_start']:
            continue

        # Store the nodes and connections in this contact
        nodes.add(c['origin'])
        nodes.add(c['destination'])
        conns[c['origin'], c['destination']] = c['cid']

    # Create the DiGraph
    G = nx.DiGraph()
    G.add_nodes_from(list(nodes))
    G.add_edges_from(list(conns.keys()))

    # Get shortest path to destination
    try:
        path = nx.dijkstra_path(G, source, target)
        return path[1], conns[path[0], path[1]], path
    except:
        return None, None, None

def get_preferred_path_from_source(source, preferred_path):
    path = preferred_path
    # select a path from source to target (excluding source)
    if preferred_path is not None and source in preferred_path:
        idx = preferred_path.index(source)
        path = preferred_path[idx:]

    return path

def find_route_energy_estimate(bundle_size=None, contact_plan=None, current_time=0,
                                nodes_state=None, source=None, target=None,
                                preferred_path=None):
    """ DEPRECATED, use ``find_route_energy_estimate3`` """
    # Initialize variables
    path       = get_preferred_path_from_source(source, preferred_path)
    energy     = {}
    contact    = {}

    # Iterate through the contact plan to get energy to transfer to neighbor
    # NOTE: Assumes that there is only one contact per (o,d) pair active at any
    #       point in time
    for link in contact_plan:
        link_origin = link['origin']
        link_destination = link['destination']
        link_bandwidth = link['bandwidth']

        if link_origin != source:
            continue

        if current_time > link['time_end'] or current_time < link['time_start']:
            continue

        try:
            energy_send = (bundle_size / link_bandwidth) * nodes_state[link_origin]['energy_usage_tx']
        except:
            energy_send = 0

        try:
            energy_receive = (bundle_size / link_bandwidth) * nodes_state[link_destination]['energy_usage_rx']
        except:
            energy_receive = 0

        # energy is total energy spent through this link
        energy[link_destination]  = energy_send + energy_receive
        contact[link_destination] = link['cid']

    # Select the neighbor of minimum energy
    n_arr, e_arr = zip(*energy.items())
    e_arr     = np.array(e_arr)
    min_e_idx = e_arr == e_arr.min()

    # If you don't have a tie, return it
    if min_e_idx.sum() == 1:
        idx = e_arr.argmin()
        selected   = n_arr[idx]
        contact_id = contact[selected]
        return selected, contact_id, None

    # Get the nodes that tied in energy
    tied = n_arr[min_e_idx]

    # Look for their position in the preferred path
    pos = [path.index(n) if n in path else float('inf') for n in tied]

    # See if there is any occurrence. If there is not, return one at random
    if sum(pos) == float('inf'):
        selected = tied[0]
        contact_id = contact[selected]
        return selected, contact_id, None

    #
    best_idx = np.array(pos).argmax()
    selected = tied[best_idx]
    contact_id = contact[selected]

    return selected, contact_id, None

def find_route_energy_estimate2(bundle_size=None, contact_plan=None, current_time=0,
                                nodes_state=None, source=None, target=None,
                                preferred_path=None):
    """
    DEPRECATED, USE ``find_route_energy_estimate3``

    In this protocol, a vehilce i selects the immediate neighbor j (i > j) that
    1) is connected directly to the source vehicle i (i > j),
    2) that requires the lowest amount of energy to transfer (energy(i,j), and
    3) that is the closest to the mouth of the cave. In this case, we consider
    the source vehicle's transmission energy usage rate, r_tx(i) (J/s) and the target
    receving energy usage rate $r_rx_{j}.  The energy required to send data d(k)
    from vehicle i to vehicle j with bandwidth bw(i,j) would be
    energy(i,j) = (r_tx(i) + r_rx(j))*(size(d(k))/bw(i,j)), where size(d(k))/bw(i,j)
    refers to the duration of the transfer. This approach would require
    that neibours vehicles share their energy usage rates for sending and receiving data.
    """
    selected = None
    contact_id = None
    path = get_preferred_path_from_source(source, preferred_path)

    energy = {}
    contact = {}

    for link in contact_plan:
        link_origin = link['origin']
        link_destination = link['destination']
        link_bandwidth = link['bandwidth']

        # check if this is an active link from the source
        if link_origin == source and current_time >= link['time_start'] and current_time < link['time_end']:
            # if a preferred path is given then check if destination is in it
            if (path is not None and link_destination in path) or (path is None):

                # get the energy needed to SEND the data given the available bandwidth
                energy_send = 0
                if link_origin in nodes_state and 'energy_usage_tx' in nodes_state[link_origin]:
                    energy_send = (bundle_size / link_bandwidth) * nodes_state[link_origin]['energy_usage_tx']
                # get the energy needed to RECEIVE the data given the available bandwidth
                energy_receive = 0
                if link_destination in nodes_state and 'energy_usage_rx' in nodes_state[link_destination]:
                    energy_receive = (bundle_size / link_bandwidth) * nodes_state[link_destination]['energy_usage_rx']

                # energy is total energy spent through this link
                energy[link_destination] = energy_send + energy_receive
                contact[link_destination] = link['cid']


    # select the node with the lowest energy
    #print(energy)
    if len(energy.values()) > 0:
        if path is None:
            # get node with min energy
            selected = min(energy, key=energy.get)
            contact_id = contact[selected]
        else:
            # get the min energy value
            min_energy = min(energy.values())
            for node in reversed(path[1:]):
                if node in energy.keys() and min_energy == energy[node]:
                    selected = node
                    contact_id = contact[selected]
                    break

    return selected, contact_id, path

def find_route_energy_estimate3(bundle_size=None, contact_plan=None, current_time=0,
                                nodes_state=None, source=None, target=None,
                                preferred_path=None):
    """ See ``find_route_energy_estimate2`` """
    # Initialize variables
    path = get_preferred_path_from_source(source, preferred_path)

    # If not path, return
    if not path: return None, None, None

    # Filter contact plan. A contact is deemed valid if:
    # 1) The contact's origin = current source
    # 2) The contact has start end not ended yet
    # 3) The contact leads to a node that is in the preferred path
    # 4) You have information about the state of the contact's origin and destination node
    idx = (contact_plan['orig'] == source) & \
          (contact_plan['tstart'] <= current_time) & (current_time < contact_plan['tend']) & \
          np.isin(contact_plan['dest'], path) & \
          np.isin(contact_plan['orig'], nodes_state['node']) & np.isin(contact_plan['dest'], nodes_state['node'])

    # If no contacts are valid, return
    if not idx.any(): return None, None, None

    # Compute energy to send data over all candidate contacts
    tx_e = np.compress(nodes_state['node']==source, nodes_state['energy_usage_tx'])[0]
    energy_send = (bundle_size / contact_plan['rate'][idx]) * tx_e

    # Compute energy to receive data over all candidate contacts
    tmp  = np.where(contact_plan['dest'][idx, np.newaxis] == nodes_state['node'][np.newaxis, :])[1]
    rx_e = np.take(nodes_state['energy_usage_rx'], tmp)
    energy_receive = (bundle_size / contact_plan['rate'][idx]) * rx_e

    # Get all contacts of minimum energy
    energy  = energy_send + energy_receive
    min_idx = np.argwhere(energy == np.amin(energy)).flatten()

    # If this condition is true, then you have a tie. Therefore, you choose the node closest to the cave's mouth.
    # To efficiently implement this behavior, we rely on the fact that nodes are numbered
    # (i.e., `node_8` < `node_9`), and the base station is named ``base_station``.
    # Therefore, you can obtain correct order just by ordering the names
    if len(min_idx) > 1:
        min_idx = np.argsort(contact_plan['dest'][idx][min_idx])

    # Grab the best contact
    selected   = np.take(contact_plan['dest'][idx], min_idx)[0]
    contact_id = np.take(contact_plan['cid'][idx], min_idx)[0]
    path       = path[path.index(selected):]

    return selected, contact_id, path

def find_route_energy_left2(bundle_size=None, contact_plan=None, current_time=0,
                                nodes_state=None, source=None, target=None,
                                preferred_path=None):
    # Initialize variables
    path = get_preferred_path_from_source(source, preferred_path)

    # If not path, return
    if not path: return None, None, None

    # Filter contact plan. A contact is deemed valid if:
    # 1) The contact's origin = current source
    # 2) The contact has start end not ended yet
    # 3) The contact leads to a node that is in the preferred path
    # 4) You have information about the state of the contact's origin and destination node
    idx = (contact_plan['orig'] == source) & \
          (contact_plan['tstart'] <= current_time) & (current_time < contact_plan['tend']) & \
          np.isin(contact_plan['dest'], path) & \
          np.isin(contact_plan['orig'], nodes_state['node']) & np.isin(contact_plan['dest'], nodes_state['node'])

    # If no contacts are valid, return
    if not idx.any(): return None, None, None

    # Compute energy to send data over all candidate contacts
    tx_e = np.compress(nodes_state['node'] == source, nodes_state['energy_usage_tx'])[0]
    energy_send = (bundle_size / contact_plan['rate'][idx]) * tx_e

    # Compute energy to receive data over all candidate contacts
    tmp  = np.where(contact_plan['dest'][idx, np.newaxis] == nodes_state['node'][np.newaxis, :])[1]
    rx_e = np.take(nodes_state['energy_usage_rx'], tmp)
    energy_receive = (bundle_size / contact_plan['rate'][idx]) * rx_e

    # Compute the energy left at each destination node
    energy_left = np.take(nodes_state['battery_level'], tmp) - (energy_send + energy_receive)

    # Select the node with more energy left in its battery
    max_idx = np.argwhere(energy_left == np.amax(energy_left)).flatten()

    # If this condition is true, then you have a tie. Therefore, you choose the node closest to the cave's mouth.
    # To efficiently implement this behavior, we rely on the fact that nodes are numbered
    # (i.e., `node_8` < `node_9`), and the base station is named ``base_station``.
    # Therefore, you can obtain correct order just by ordering the names
    if len(max_idx) > 1:
        max_idx = np.argsort(np.take(contact_plan['dest'][idx], max_idx))

    # Grab the best contact
    selected   = np.take(contact_plan['dest'][idx], max_idx)[0]
    contact_id = np.take(contact_plan['cid'][idx], max_idx)[0]
    path       = path[path.index(selected):]

    return selected, contact_id, path

def find_route_energy_left(bundle_size=None, contact_plan=None, current_time=0,
                                nodes_state=None, source=None, target=None,
                                preferred_path=None):
    """
    In this protocol, a vehile i selects the imediate neighbor j (i > j) that
    1) has a direct connection with the source vehicle,
    2) has the greatest amount of energy left after transferring the data, energy_left(j),
    and 3) that is the closest to the mouth of the cave. Here,
    energy_left(j) = battery_level(j) - r_rx(j)*(size(d(k))/bw(i,j)).
    """
    selected = None
    contact_id = None
    path = get_preferred_path_from_source(source, preferred_path)

    energy_left = {}
    contact = {}

    for link in contact_plan:
        link_origin = link['origin']
        link_destination = link['destination']
        link_bandwidth = link['bandwidth']
        # check if this is an active link from the source
        if link_origin == source and current_time >= link['time_start'] and current_time < link['time_end']:
            # if a preferred path is given then check if destination is in it
            if (path is not None and link_destination in path) or (path is None):

                # get the energy needed to SEND the data given the available bandwidth
                energy_send = 0
                if link_origin in nodes_state and 'energy_usage_tx' in nodes_state[link_origin]:
                    energy_send = (bundle_size / link_bandwidth) * nodes_state[link_origin]['energy_usage_tx']
                # get the energy needed to RECEIVE the data given the available bandwidth
                energy_receive = 0
                if link_destination in nodes_state and 'energy_usage_rx' in nodes_state[link_destination]:
                    energy_receive = (bundle_size / link_bandwidth) * nodes_state[link_destination]['energy_usage_rx']


                energy_capacity = 0
                energy_level = 0
                if link_destination in nodes_state and \
                       'battery_capacity' in nodes_state[link_destination] and \
                       'battery_level' in nodes_state[link_destination]:
                    energy_capacity = nodes_state[link_destination]['battery_capacity']
                    energy_level = nodes_state[link_destination]['battery_level']

                # set energy left
                energy_left[link_destination] = energy_level - energy_receive
                contact[link_destination] = link['cid']


    # select the node with the lowest energy
    # print(energy_left)
    if len(energy_left.values()) > 0:
        if path is None:
            # get node with max energy left
            selected = max(energy_left, key=energy_left.get)
            contact_id = contact[selected]
        else:
            # get the min energy value
            max_energy_left = max(energy_left.values())
            for node in reversed(path[1:]):
                if node in energy_left.keys() and max_energy_left == energy_left[node]:
                    selected = node
                    contact_id = contact[selected]
                    break
        # check id the max energy left is 0 or less, if no there is good option/hop
        if energy_left[selected] <= 0:
            selected = None
            contact_id = None
            path = None

    return selected, contact_id, path

def find_route_bandwidth_threshold(bundle_size=None, contact_plan=None, current_time=0,
                                    nodes_state=None, source=None, target=None,
                                    threshold=float('inf'), preferred_path=None):
    """ Selects the next vehicle to send the data towards the target node based on the highest
        bandwith.
        The argument preferred_path is expected to provide a path towards thet target from the source.
    """
    selected = None
    contact_id = None
    path = get_preferred_path_from_source(source, preferred_path)

    # check whether the target is in the preferred path
    # if target not in path:
    #     return None, path

    bandwidths = {}
    contact = {}

    for link in contact_plan:
        if link['origin'] == source and current_time >= link['time_start'] and current_time < link['time_end']:
            # if a preferred path is given then check if destination is in it
            if (path is not None and link_destination in path) or (path is None):
                bandwidths[link['destination']] = link['bandwidth']
                contact[link['destination']] = link['cid']

    # select the first node in the path with a bw that meets the threshold
    if len(bandwidths.values()) > 0:
        for node in path[1:]:
            if node in bandwidths.keys() and bandwidths[node] >= threshold:
                selected = node
                contact_id = contact[node]
                break

    return selected, contact_id, path


def find_route_highest_bandwidth(bundle_size=None, contact_plan=None, current_time=0,
                               nodes_state=None, source=None, target=None,
                               preferred_path=None):
    """ Selects the next vehicle to send the data towards the target node based on the highest
        bandwith.
        The argument preferred_path is expected to provide a path towards thet target from the source.
    """
    selected = None
    contact_id = None
    path = get_preferred_path_from_source(source, preferred_path)

    # check whether the target is in the preferred path
    # if target not in path:
    #     return None, path

    bandwidths = {}
    contact = {}

    for link in contact_plan:
        if link['origin'] == source and current_time >= link['time_start'] and current_time < link['time_end']:
            # if a preferred path is given then check if destination is in it
            if (path is not None and link_destination in path) or (path is None):
                bandwidths[link['destination']] = link['bandwidth']
                contact[link['destination']] = link['cid']

    # get the max bandwidth
    if len(bandwidths.values()) > 0:
        selected = max(bandwidths, key=bandwidths.get)
        contact_id = contact[selected]
        if bandwidths[selected] == 0:
            selected = None
            contact_id = None
            path = None

    return selected, contact_id, path


def find_route_backlog_threshold(bundle_size=None, contact_plan=None, current_time=0,
                                    nodes_state=None, source=None, target=None,
                                    threshold=0, preferred_path=None):
    """ Selects the next vehicle to send the data towards the target node based on the data backlog
        on the nodes in the network.
        The argument preferred_path is expected to provide a path towards thet target from the source.
    """
    selected = None
    contact_id = None
    path = get_preferred_path_from_source(source, preferred_path)

    # check if the data backlog threshold constraint is met at the source
    if nodes_state[source]['data_backlog'] < threshold:
        return None, None, path

    backlogs = {}
    contact = {}

    for link in contact_plan:
        if link['origin'] == source and current_time >= link['time_start'] and current_time < link['time_end']:
            # if a preferred path is given then check if destination is in it
            if (path is not None and link_destination in path) or (path is None):
                backlogs[link['destination']] = nodes_state[link['destination']]['data_backlog']
                contact[link['destination']] = link['cid']

    # get the min bandwidth
    min_backlog = min(backlogs.values())

    # get the node with min  backlog closet to the backlog
    if len(bandwidths.values()) > 0:
        for node in reversed(path[1:]):
            if node in backlogs.keys() and min_backlog == backlogs[node]:
                selected = node
                contact_id = contact[selected]
                break

    return selected, contact_id, path
