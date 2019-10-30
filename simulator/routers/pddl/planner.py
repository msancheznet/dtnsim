#!/usr/bin/python

#########################################################################################
# Copyright 2018, by the California Institute of Technology. ALL RIGHTS RESERVED.       #
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
import numpy
import json
import subprocess
from threading import Thread, Event
import time
from tempfile import mkdtemp
# from subprocess32 import check_output, TimeoutExpired
from easyprocess import EasyProcess


class PDDLPlanner(Thread):
    """PDDL-based Planner
    """

    def __init__(self, domain_file, problem, parameters={}, timeout=None, verbose=False):
        Thread.__init__(self)
        self.domain_file = domain_file
        self.problem = problem
        self.parameters = parameters
        self.optimize = True if 'optimize' in parameters.keys() and parameters['optimize'] else False
        self.incremental = True if 'incremental' in parameters.keys() and parameters['incremental'] else False
        self.result = None
        self.timeout = timeout
        self.timeout_happened = False
        # TODO: set the planner from a config file?
        #       Here the selected planner is hard coded
        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.planner_path = os.path.join(self.script_dir, 'planners', 'optic-clp')
        self.verbose = verbose

    def _verbprint(self, string):
        if self.verbose:
            print(string)

    def run(self):
        """ Runs PDDL planner given the target domain and problem.
        """
        start_time = time.time()
        self._verbprint('Calling the planner.')
        # print(self.planner_path)
        self.result = None

        if not self.incremental:

            # Write out the domain and problem files.
            temp_dir = mkdtemp(prefix='planner_temp')
            # domain_file = self.domain_file
            domain_file = os.path.join(self.script_dir, 'model', 'domain.pddl')
            # with open(domain_file, 'w') as f:
            #     f.write(self.domain_file_contents())
            # problem_file = os.path.join(self.script_dir, 'model', 'problem.pddl')
            problem_file = os.path.join(temp_dir, 'problem.pddl')
            with open(problem_file, 'w') as f:
                f.write(self.problem.to_pddl())

            # build command
            command = []
            #  command: timeout elelements
            # command.extend(['timeout', str(self.timeout)])
            #  command: planner
            command.append(self.planner_path)
            #  command: planner's optional parameters

            if not self.optimize:
                command.append('-N')
            command.extend([domain_file, problem_file])
            self._verbprint('Command line: ' + str(command))

            # run command
            #  using easyprocess
            process = EasyProcess(command)
            out = process.call(timeout=self.timeout).stdout
            if process.timeout_happened:
                self._verbprint('TIME OUT!!')
                self.timeout_happened = True
            #  using subprocess32
            # try:
            #     out = check_output(command, timeout=3)
            # except TimeoutExpired as e:
            #     print e
            #     out = e.output
            #     self.timeout_happened = True

        else:

            if 'mimimal_total_reward' not in self.problem.specs['Options']:
                self.problem.specs['Options'].update({'mimimal_total_reward': 0})

            max_reward_value = self.problem.get_maximun_reward_value()
            max_reward_reached = False

            current_total_reward = self.problem.specs['Options']['mimimal_total_reward']
            reward_increment = min([reward for task, reward in self.problem.specs['Tasks']['TaskReward'].items() if reward > 0])

            current_timeout = self.timeout - (time.time() - start_time)
            iteration_index = 0

            while current_timeout > 0 and not max_reward_reached:
                self._verbprint('##########################')
                self._verbprint('Iteration: ' + str(iteration_index+1))
                print('Iteration: ' + str(iteration_index+1))
                self._verbprint(max_reward_value)
                self._verbprint('##########################')
                # Write out the domain and problem files.
                temp_dir = mkdtemp(prefix='planner_temp')
                # domain_file = self.domain_file
                domain_file = os.path.join(self.script_dir, 'model', 'domain.pddl')
                # with open(domain_file, 'w') as f:
                #     f.write(self.domain_file_contents())
                # problem_file = os.path.join(self.script_dir, 'model', 'problem.pddl')
                problem_file = os.path.join(temp_dir, 'problem.pddl')
                with open(problem_file, 'w') as f:
                    f.write(self.problem.to_pddl())

                # build command
                command = []
                #  command: timeout elelements
                # command.extend(['timeout', str(self.timeout)])
                #  command: planner
                command.append(self.planner_path)
                #  command: planner's optional parameters


                self._verbprint('##############')
                command.append('-N')
                command.extend([domain_file, problem_file])
                self._verbprint('Command line: ' + str(command))

                # compute time left for the planner (seconds)
                current_timeout = self.timeout - (time.time() - start_time)
                self._verbprint('Iteration timeout: ' + str(current_timeout) + ' s')
                if current_timeout <=0:
                    break
                # run command
                #  using easyprocess
                process = EasyProcess(command)
                out = process.call(timeout=current_timeout).stdout
                if process.timeout_happened:
                    self._verbprint('TIME OUT!!')
                    self.timeout_happened = True
                    break


                plan_start_index = out.find(';;;; Solution Found')
                if plan_start_index != -1:
                    # print(out[plan_start_index:])
                    self.result = self.pddl_plan_to_schedule(out[plan_start_index:])
                    evaluation = evaluate_schedule(PUFFERPDDLTranslator.clean_up_schedule(self.result), self.problem.specs)
                    self._verbprint(evaluation)

                    if evaluation['total_task_reward'] >= max_reward_value:
                        self._verbprint('MAX REWARD REACHED!!! reward = ' + str(max_reward_value))
                        max_reward_reached = True
                        break

                    # increment reward
                    self.problem.specs['Options']['mimimal_total_reward'] = evaluation['total_task_reward'] + reward_increment

                iteration_index += 1


        # get output plan
        # print out
        if self.optimize and not self.incremental:
            planner_output = out.split('\n\n')
            self._verbprint(planner_output)
            for i in range(len(planner_output) - 1, -1, -1):
                plan_start_index = planner_output[i].find('; Plan found')
                if plan_start_index == -1:
                    plan_start_index = planner_output[i].find(';;;; Solution Found')

                if plan_start_index != -1:
                    self.result = self.pddl_plan_to_schedule(planner_output[i][plan_start_index:])
                    self._verbprint(planner_output[i][plan_start_index:])
                    return
        else:
            plan_start_index = out.find(';;;; Solution Found')
            if plan_start_index != -1:
                # print(out[plan_start_index:])
                self.result = self.pddl_plan_to_schedule(out[plan_start_index:])
                self._verbprint(out[plan_start_index:])
                return




    def pddl_plan_to_schedule(self, plan_str):
        """ Translates a PDDL plan (string) into a dictionary representation
            of a schedule/plan.
        """
        # print '-------'
        # print plan_str
        # print '-------'
        pddl_action_list = plan_str.splitlines()
        pddl_action_list = filter(lambda x: not x.startswith(';'), pddl_action_list)
        pddl_action_list = filter(lambda x: ': (' in x , pddl_action_list)
        # plan_lines = map(lambda x: x.split(';')[0], plan_lines)
        pddl_action_list = filter(lambda x: not x == '', pddl_action_list)
        # print pddl_action_list

        schedule = {'tasks':[]}
        index = 0
        for pddl_action in pddl_action_list:
            # expected format for non_transfer actions: 'start_time: (perform_<> agent task_name data_name input_data_type output_data_type)  [duration]'
            # expected format for transfer actions: 'start_time: (trasnfer_data agent_from agent_to data_name data_type)  [duration]'
            start_time = float(pddl_action.split(':')[0])
            duration = float(pddl_action[pddl_action.find('[')+1:pddl_action.find(']')])
            action_str = pddl_action[pddl_action.find('(')+1:pddl_action.find(')')]
            action_params = action_str.split(' ')
            task_name = None
            agent_name = None
            params = {}
            if action_params[0].startswith('transfer'):
                task_name = action_params[0]
                agent_name = action_params[1]
                params['agent'] = agent_name
                params['sender'] = action_params[1]
                params['receiver'] = action_params[2]
                params['data'] = action_params[3]
            else:
                print('PARSER ERROR: could not parse pddl action (' + action_str + ')')

            # create task in the schedule
            if task_name is not None:
                task = {}
                task['id'] = str(index) #TODO: generate id automatically
                task['name'] = task_name
                task['start_time'] = start_time
                task['duration'] = duration
                task['params'] = params
                schedule['tasks'].append(task)

                index += 1


        # print(schedule)

        return schedule


    def save_json_result(self, output_file):
        if self.result is not None:
            content = json.dumps(self.result, indent=4)
            with open(output_file, 'w') as fp:
                fp.write(content)
        else:
            print('ERROR: Planner result is None. Not able to save it to json file.')

    def schedule(self):
        self.start()
        # block until thread is alive
        # planner.join()
        while self.is_alive():
            pass
        #print('We are done!')
        #print('Results:')
        pddl_schedule = self.result
        return pddl_schedule
