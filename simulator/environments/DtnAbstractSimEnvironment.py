import abc
import logging
import simpy
import os
from pathlib import Path
from threading import Thread
import time
import traceback

from simulator.utils.time_utils import sec2hms

class SimEnvironment(simpy.Environment, metaclass=abc.ABCMeta):
    section_length = 100
    logger_name = 'DTN Simulation'
    header_msg = '[{:<6}| {:<15}]: '
    track_msg  = header_msg+'{} vs. {} (x{:.2f})'
    init_msg   = header_msg+'Initializing Simulation "{}" (Seed = {})'
    end_msg    = header_msg+'Total Simulation Time = {}'
    del_msg    = header_msg+'Simulation Environment Deleted'

    def __init__(self, config):
        super(SimEnvironment, self).__init__()
        self.config      = config
        self.config_file = config['globals'].config_file
        self.sim_id      = config['globals'].id
        self.do_log      = config['globals'].log
        self.do_track    = config['globals'].track
        self.monitor     = config['globals'].monitor
        self.log_file    = config['globals'].outdir / config['globals'].logfile
        self.until       = config['scenario'].until

    def track_simulation(self, dt=1e1, until=None):
        if self.do_track == False: return
        self._track_thread = Thread(target=self._track_simulation, args=(dt, until))
        self._track_thread.start()

    def _track_simulation(self, dt, until):
        # Initialize variables
        msg = self.__class__.track_msg
        elapsed = 0.0
        self._track_shutdown = False

        # Sleep for a second to give time for the simulation to start
        time.sleep(1)

        while len(self._queue) > 0 and self._track_shutdown == False:
            time.sleep(dt)
            elapsed += dt
            sim_time = self.now
            if until: self._track_shutdown = sim_time >= until
            sim_rate = sim_time / elapsed
            print(msg.format(os.getpid(), self.sim_id, sec2hms(elapsed),
                             sec2hms(sim_time), sim_rate))

            # If the simulation is over, stop the thread
            if not self.is_running:
                break

            #DEBUG: If you uncomment it will tell you which process is running.
            #Useful if sim is not moving forward
            #print(self.active_process)

    @property
    def is_running(self):
        # According to Simpy docs, if peek returns inf, then there are no more
        # events scheduled
        return self.peek() != float('inf')

    def run(self, *args, **kwargs):
        self.new_log_section(title='RUN SIMULATION')
        try:
            self.track_simulation(dt=self.config['globals'].track_dt,
                                  until=self.until)
            kwargs['until'] = self.until
            super(SimEnvironment, self).run(*args, **kwargs)
        except Exception as e:
            self.new_log_section(title='SIMULATION EXCEPTION')
            self.log(traceback.format_exc(), header=False)
            self.close_logger()
            raise e
        finally:
            if self.do_track:
                self._track_shutdown = True
                self._track_thread.join()

    def initialize_logger(self):
        # If no need to do log, skip
        if self.do_log == False: return

        # Initialize logger
        self.logger = logging.getLogger(self.__class__.logger_name)

        # Add the file handler
        self.fh = logging.FileHandler(self.log_file, mode='w')
        self.fh.setLevel(logging.DEBUG)
        self.logger.addHandler(self.fh)

        # Start log file
        self.new_log_section(self.__class__.logger_name + " Log Start")

    def log(self, msg, *args, **kwargs):
        # If no need to do log, skip
        if self.do_log == False: return

        # Build log message
        header = True if 'header' not in kwargs else kwargs['header']
        header = 't={0:.3f}:\t'.format(self.now) if header == True else ''
        if len(args) > 0: msg = msg.format(*args)
        self.logger.warning(header + msg)

    def error(self, msg, *args, **kwargs):
        # If not needed, skip
        if self.do_log == False: return

        # Build error log message
        header = True if 'header' not in kwargs else kwargs['header']
        header = 'ERROR during simulation:\t' if header == True else ''
        if len(args) > 0: msg = msg.format(*args)
        self.logger.warning(header + msg)

    def new_line(self):
        # If not needed, skip
        if self.do_log == False: return

        # Add new line
        self.logger.warning('')

    def close_logger(self):
        # If no need to do log, skip
        if self.do_log == False: return

        # End log file
        self.new_log_section(self.__class__.logger_name + " Log End")

        self.fh.close()
        self.logger.removeHandler(self.fh)

    def new_log_section(self, title='', new_break=True):
        """ Create a new section in the logger

            :param str title: Section title
            :param bool new_break: If True, a break is added to the log file.
        """
        # If no need to do log, skip
        if self.do_log == False: return

        # Add a new break line
        if new_break == True:
            self.logger.warning(' ')
            self.logger.warning(' ')

        # Display section title
        s = self.__class__.section_length
        self.logger.warning('=' * s + ' ' + title + ' ' + '=' * s)

    @abc.abstractmethod
    def initialize(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def finalize_simulation(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def validate_simulation(self, *args, **kwargs):
        pass

    def __str__(self):
        return '<DtnSimEnvironment t={}>'.format(self.now)

    def __repr__(self):
        return '<DtnSimEnvironment t={} at {}>'.format(self.now, hex(id(self)))