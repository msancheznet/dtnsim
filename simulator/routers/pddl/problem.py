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


class PDDLProblem(object):
    """PDDL Problem object

    Attributes:
        specs:
        init_state:
        goal:
        metric:
    """

    def __init__(self, bundle_size=None, contact_plan=None, current_time=0,
                       nodes_state=None, source=None, target=None, verbose=False):
        self.bundle_size = bundle_size
        self.contact_plan = contact_plan
        self.current_time = current_time
        self.nodes_state = nodes_state
        self.source = source
        self.target = target
        self.horizon = 3600 # secs (1 hour)
        self.domain_name = 'DTN_Data_Routing_v4'
        self.initialize_variables()

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.verbose = verbose

    def initialize_variables(self):
        self.objects = []
        self.init_state = []
        self.goals = []
        self.metric = []

    def to_pddl(self):
        """ Translates the problem specs dict into a pddl problem
            representation (string).
        """
        self.initialize_variables()

        backlog_data = {}

        # OBJECTS
        data_type_objs = []
        # agents
        for vehicle_name, state in self.nodes_state.items():
            data_type_objs.append(vehicle_name + ' - Agent')
            # gather data backlog in the network
            backlog_data[vehicle_name] = []
            if 'data' in state:
                for data in state['data']:
                    data_type_objs.append(vehicle_name + ' - Agent')
                    if vehicle_name != self.source:
                        backlog_data[vehicle_name].append(data)



        # data
        data_type_objs.append('target_data - Data')
        # backlog data in the network
        if self.verbose:
            print(backlog_data)
        for vehicle_name, data_list in backlog_data.items():
            for data in data_list:
                data_name = 'data_'+str(data['id'])
                data_type_objs.append(data_name + ' - Data')

        self.objects.extend(data_type_objs)


        # INITIAL STATE
        # vehicles
        for vehicle_name, state in self.nodes_state.items():
            related_state = [';;  - ' + vehicle_name, '(idle ' +vehicle_name+ ')']
            related_state.append('(= (battery_level ' +vehicle_name+ ') '+str(state['battery_level'])+ ')')
            related_state.append('(= (battery_capacity ' +vehicle_name+ ') '+str(state['battery_capacity'])+ ')')
            related_state.append('(= (energy_usage_tx ' +vehicle_name+ ') '+str(state['energy_usage_tx'])+ ')')
            related_state.append('(= (energy_usage_rx ' +vehicle_name+ ') '+str(state['energy_usage_rx'])+ ')')
            self.init_state.extend(related_state)

        # data
        related_state = [';;  - target_data', '(at target_data '+self.source+ ')']
        related_state.append('(= (size target_data) '+str(self.bundle_size)+ ')')
        self.init_state.extend(related_state)
        for vehicle_name, data_list in backlog_data.items():
            for data in data_list:
                data_name = 'data_'+str(data['id'])
                related_state = [';;  - ' + data_name, '(at ' +data_name + ' '+vehicle_name+ ')']
                related_state.append('(= (size ' +data_name+ ') '+str(data['size'])+ ')')
                self.init_state.extend(related_state)


        # Network Topology
        self.init_state.append('')
        self.init_state.append(';; Network Topology')
        for link in self.contact_plan:
            # consider only bw > 0 and contacts that are within the specified horizon
            if link['bandwidth'] > 0 and (link['time_start'] < self.current_time + self.horizon):
                # current active contact
                if self.current_time >= link['time_start'] and self.current_time < link['time_end']:
                    self.init_state.append('(connected '+link['origin']+' '+link['destination']+')')
                    self.init_state.append('(= (bandwidth '+link['origin']+' '+link['destination']+') '+ '{0:.2f}'.format(1/link['bandwidth'])+')')
                # future active contact
                elif self.current_time < link['time_start'] and self.current_time < link['time_end']:
                    start_time = link['time_start'] - self.current_time
                    self.init_state.append('(at '+str(start_time)+' (connected '+link['origin']+' '+link['destination']+'))')
                    self.init_state.append('(at '+str(start_time)+' (= (bandwidth '+link['origin']+' '+link['destination']+') '+ '{0:.2f}'.format(1/link['bandwidth'])+'))')

                # set link end
                end_time = link['time_end'] - self.current_time
                if end_time > self.horizon:
                    end_time =  self.horizon
                self.init_state.append('(at '+str(end_time)+' (not (connected '+link['origin']+' '+link['destination']+')))')
                self.init_state.append('(at '+str(end_time)+' (= (bandwidth '+link['origin']+' '+link['destination']+') 0))')



        self.init_state.append('')
        self.init_state.append(';;  - global state variables')
        # initial energy variables values for optimization
        self.init_state.append('(= (total_energy) 0)')
        # initial value for energy
        self.init_state.append('(= (energy_left_penalty) 0)')
        # bandwidth threshold
        self.init_state.append('(= (bandwidth_threshold) 1)')



        # GOAL
        self.goals.append('(at target_data '+self.target+')')
        for vehicle_name, data_list in backlog_data.items():
            for data in data_list:
                data_name = 'data_'+str(data['id'])
                self.goals.append('(at ' +data_name + ' '+data['destination']+ ')')


        # Metric
        # build cost function/metric expression
        # metric_str = '(+ (total_energy) (energy_left_penalty))'
        metric_str = '(+ (+ (total_energy) (energy_left_penalty)) (total-time))'
        # maximize or minimize
        metric_approach = 'minimize'

        # put all together
        pddl = '(define (problem Problem1) \n ' + \
               '    (:domain '+self.domain_name+') \n' + \
               '    (:objects \n' + \
               '        ' + '\n        '.join(self.objects) + '\n' + \
               '    ) \n'+ \
               '    (:init \n' + \
               '        ' + '\n        '.join(self.init_state) + '\n' + \
               '    ) \n' + \
               '    (:goal \n' + \
               '        (and \n' + \
               '            ' + '\n            '.join(self.goals) + '\n' + \
               '        )\n' + \
               '    )\n' + \
               '    (:metric ' +metric_approach+ ' ' +metric_str+ ')\n' + \
               ')'
        if self.verbose:
            print(pddl)

        # TESTING
        # problem_file = os.path.join(self.script_dir, 'model', 'problem.pddl')
        # with file(problem_file) as f:
        #     pddl = f.read()

        return pddl
