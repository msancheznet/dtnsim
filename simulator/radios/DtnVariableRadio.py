"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/24/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

import numpy as np
import pandas as pd

from simulator.core.DtnSemaphore import DtnSemaphore
from simulator.radios.DtnBasicRadio import DtnBasicRadio

class DtnVariableRadio(DtnBasicRadio):

    _data = {}

    def reset(self):
        # Reset static variable
        self.__class__._data = {}

    def initialize(self, datarate_file=None, **kwargs):
        # Define the data rate as NaN
        kwargs['rate'] = np.nan

        # Initialize data rate profile
        file = self.config['globals'].indir/datarate_file

        # If this data is already loaded, use it
        try:
            df = self._data[self.parent.nid]
        except KeyError:
            df = self.load_data_rate(file)

        # Depack and transform all to numpy arrays
        self.dr = df.copy(deep=True).to_dict(orient='list')
        for k in self.dr.keys(): self.dr[k] = np.array(self.dr[k])
        self.dr['t'] = df.index.values

        # Call parent initializer
        super(DtnVariableRadio, self).initialize(**kwargs)

        # Create a semaphore to signal when the radio has >0 data rate
        self.active = {n: DtnSemaphore(self.env, green=False) for n in self.dr if n != 't'}

        # Start radio data rate monitor
        for dest in self.active:
            self.env.process(self.datarate_monitor(dest))

    def load_data_rate(self, file):
        # Load depending on file type
        if file.suffix == '.xlsx':
            df = pd.read_excel(file, header=[0, 1], index_col=0)
        elif file.suffix == '.h5':
            df = pd.read_hdf(file, key='data_rate')
        else:
            raise IOError('Only .xlsx and .h5 files can be loaded')

        # Get the timelines for this node
        df = df.xs(self.parent.nid, axis=1, level=0)

        # Store data
        self._data[self.parent.nid] = df

        return df

    def datarate_monitor(self, dest):
        # If no data for this destination, exit
        if dest not in self.dr: yield self.env.exit()

        # Initialize variables
        sm = self.active[dest]

        # Iterate over data rate profile
        for t, dr in zip(self.dr['t'], self.dr[dest]):
            # Wait until its time to update
            yield self.env.timeout(max(0, t-self.t))

            # If no data rate and already red, continue
            if dr == 0 and sm.is_red:
                continue

            # If data rate == 0 and green, turn red
            if dr == 0 and sm.is_green:
                sm.turn_red()
                continue

            # If you reach this point, turn green if red
            if sm.is_red: sm.turn_green()

    def run(self):
        while self.is_alive:
            # Get the next segment to transmit
            item = yield from self.in_queue.get()

            # Depack item
            neighbor, message, peer, direction = item

            # Wait until this connection is active
            if self.active[neighbor].is_red:
                yield self.active[neighbor].green

            # Get the connection to send this message through
            conn = self.outcons[neighbor]

            # Get the data rate for this radio
            tx_time = self.get_tx_time(neighbor, message)

            # Apply delay for radio to transmit entire segment
            yield self.env.timeout(tx_time)

            # Count the energy consumed
            self.energy += message.num_bits * self.J_bit

            # Transmit the message through the connection.
            self.send_through_connection(message, conn, peer, direction)

    def get_tx_time(self, dest, message):
        # Initialize variables
        t, dr = self.dr['t'], self.dr[dest]

        # Find the first instant that exceeds current time
        idx1 = (t > self.t).argmax()

        # Figure out how much data you could send between now and this first instant
        dv = (t[idx1] - self.t) * dr[idx1 - 1]

        # If that is enough data rate, you are done
        if dv >= message.data_vol:
            return message.data_vol/dr[idx1-1]

        # Clip time series to only the relevant parts
        elapsed  = t[idx1]-self.t
        t, dr    = t[idx1:]-t[idx1], dr[idx1:-1]
        data_vol = np.ceil(message.data_vol - dv)

        # Otherwise, check how long it will take. First, compute the amount of data
        # sent over the connection cumulatively
        dv = np.cumsum(np.diff(t) * dr)

        # Find the instant in time where dv exceeds the message dv
        idx2 = (dv >= data_vol)

        # If it never sends this data volume, return infinite
        if not idx2.any():
            print(self.parent.nid, 'radio is stuck forever')
            return float('inf')

        # Get the first index (i.e. the first instant in time) where you will have sent
        # the message
        idx2 = idx2.argmax()

        # Compute the amount of extra data that will have sent by the end of idx2+1.
        # You need to subtract it.
        extra_dv = dv[idx2]-data_vol

        # Compute the amount of time to send this ddv bits
        Ttx = elapsed + t[idx2+1] - extra_dv/dr[idx2]

        return Ttx