"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/24/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

from .DtnAbstractMobilityModel import DtnAbstractMobilityModel
import pandas as pd

class DtnPlannedMobilityModel(DtnAbstractMobilityModel):
    """ Differences between Planned and Scheduled Mobility Model:

        1) Scheduled model requires separate contact plan and ranges
        2) Scheduled model does not have data rate of contacts as
           inputs, it inherits it from the radios that are defined

        A planned mobility model is more strict than a scheduled model.
        It dictates the data rates of the radios. Therefore, you cannot
        use a ``DtnBasicRadio`` with it. Instead, use a ``DtnVariableRadio``
        that will adapt its data rate as indicated by the contact plan.
    """
    def __init__(self, env, props):
        # Call parent constructor
        super(DtnPlannedMobilityModel, self).__init__(env, props)

        # Initialize paths
        indir = self.config['globals'].indir
        self.contact_file = indir / self.props.contacts

    def initialize(self):
        # Read the file
        if self.contact_file.suffix == '.xlsx':
            cp = pd.read_excel(self.contact_file)
        elif self.contact_file.suffix == '.csv':
            converters = {'tstart': lambda x: pd.to_datetime(x),
                          'tend': lambda x: pd.to_datetime(x)}
            cp = pd.read_csv(self.contact_file, sep=',', index_col=0, converters=converters)
        else:
            raise IOError(f'Contact plan {self.contact_file} cannot be loaded.')

        # Transform to relative time
        cp.tstart = (cp.tstart - self.epoch).dt.total_seconds()
        cp.tend = (cp.tend - self.epoch).dt.total_seconds()
        cp['capacity'] = cp.duration * cp.rate

        # Check validity
        self.check_cp_validity(cp)

        # Sort columns as expected by DtnCgrBasicRouter
        cp = cp[['orig', 'dest', 'tstart', 'tend', 'duration',
                 'range', 'rate', 'capacity']]

        # Save data
        self.contacts_df = cp

    def check_cp_validity(self, cp):
        if (cp.tstart < 0).any() or (cp.tend < 0).any():
            raise ValueError('Contact plan cannot have contacts starting or ending before 0 sec.'
                             'This is most likely caused by a mismatch between the contact/range file'
                             'and the simulation epoch.')
        if (cp.rate < 0).any():
            raise ValueError('Contact plan cannot have a contact with a data rate < 0')
        if (cp.range < 0).any():
            raise ValueError('Contact plan cannot have a contact with a range  < 0')