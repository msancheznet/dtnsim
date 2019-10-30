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
import os
# import networkx as nx
#import copy

# You can only use PDDL on linux
if sys.platform != 'linux':
    raise RuntimeError('PDDL can only run on Linux')

import pdb

from simulator.routers.pddl.problem import PDDLProblem
from simulator.routers.pddl.planner import PDDLPlanner


def find_route_pddl(bundle_size=None, contact_plan=None, current_time=0,
                                nodes_state=None, source=None, target=None,
                                preferred_path=None):
    """
    In this protocol, we translate the energy-aware routing problem to a
    PDDL problem instance.
    """
    selected = None
    contact_id = None
    path = None

    problem = PDDLProblem(bundle_size, contact_plan, current_time, nodes_state, source, target)
    pddl = problem.to_pddl()

    #if target == 'node_1':
    #    print(pddl)

    # call planner
    solverParameters = {'optimize': True}
    planner = PDDLPlanner(None,problem,parameters=solverParameters,timeout=10, verbose=False)
    planner.start()
    # block until thread is alive
    # planner.join()
    while planner.is_alive():
       pass
    # print('We are done!')
    # print('Results:')

    #if target == 'node_1':
    #    print(planner.result)
    #    pdb.set_trace()

    selected, contact_id, path = schedule_to_data_path(planner.result, contact_plan, current_time, source, target)

    return selected, contact_id, path


def schedule_to_data_path(schedule, contact_plan, current_time, source, target):
    """
    Extract selected hop, contact id and path from pddl plan output
    """
    selected = None
    contact_id = None
    path = None

    if schedule is None:
        return selected, contact_id, path

    if len(schedule['tasks']) > 0:
        path = [source]

    for task in schedule['tasks']:
        # get selected hop
        if task['params']['agent'] == source and task['params']['data'] == 'target_data' and selected is None:
                selected = task['params']['receiver']

                # find contact id
                task_start_time = current_time + task['start_time']
                for link in contact_plan:
                    if link['bandwidth'] > 0 and link['origin'] == source and link['destination'] == selected:
                        # check if that is the corresponding active contact
                        if task_start_time >= link['time_start'] and task_start_time < link['time_end']:
                            contact_id = link['cid']
                            break
        if path is not None and task['params']['data'] == 'target_data':
            path.append(str(task['params']['receiver']))


    return selected, contact_id, path
