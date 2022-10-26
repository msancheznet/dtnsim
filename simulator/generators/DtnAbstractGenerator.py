import abc
import pandas as pd
from simulator.core.DtnCore import Simulable

class DtnAbstractGenerator(Simulable, metaclass=abc.ABCMeta):
    """ Abstract class for all generators. To subclass it, implement

        1) The ``initialize`` method. Typically, use ``self.props`` to initialize
           this generator and then call ``self.env.process(self.run())``
        2) The ``run`` method should create Bundles and then call ``self.parent.forward(bundle)``
           Also, call the ``self.monitor_new_bundle`` to record the generation of bundles
    """
    # Each generator creates bundles for flow identified by a ``fid``. This is unique across all
    # generators. NOTE: The ``DtnMarkovBundleGenerator`` behaves differently
    _fid_counter = 0

    def __init__(self, env, parent, props):
        super(DtnAbstractGenerator, self).__init__(env)

        # Initialize variables
        self.monitor = self.env.monitor
        self.parent  = parent
        self.props   = props

        # Get the flow id for this generator
        self.assign_fid()

        # If no monitoring, return
        if self.monitor == False: return

        # Counter for bundles sent
        self.sent = []

    def reset(self):
        # Reset static variables
        self.__class__._fid_counter = 0

    @property
    def is_alive(self):
        return self.parent.is_alive

    def assign_fid(self):
        # Get the flow id for this generator
        self.__class__._fid_counter += 1
        self.fid = self.__class__._fid_counter

    @abc.abstractmethod
    def initialize(self):
        pass

    @property
    def is_alive(self):
        return self.parent.is_alive

    @abc.abstractmethod
    def run(self, *args, **kwargs):
        pass

    def list_bundles(self):
        """ Return a pandas.DataFrame index by (bid, cid) that
            describes all bundles sent by this generator

            .. Tip:: To see what information is available per
                     bundle, look at ``DtnBundle.Bundle.export_vars``
        """
        if not self.monitor or len(self.sent) == 0:
# 20220307: ichappel@ida.org
# fix for deprecated 'labels' parameter, now 'codes' in pandas 4.0.1
#            idx = pd.MultiIndex(levels=[[],[]], labels=[[],[]], names=['bid', 'cid'])
            idx = pd.MultiIndex(levels=[[],[]], codes=[[],[]], names=['bid', 'cid'])
            df  = pd.DataFrame(index=idx)
        else:
            df = pd.DataFrame([b.to_dict() for b in self.sent]) if self.monitor else pd.DataFrame()
            df.set_index(['bid', 'cid'], drop=True, inplace=True)
        return df

    def monitor_new_bundle(self, bundle):
        if self.monitor == False: return
        self.sent.append(bundle)

    @abc.abstractmethod
    def predicted_data_vol(self):
        """ The predicted data volume [bits] that this generator
            should generate over the course of the simulation
        """
        pass

    def generated_data_vol(self):
        """ Return the total data volume in [bits] generated
            during the simulation
        """
        return sum(b.data_vol for b in self.sent) if self.monitor else -1
