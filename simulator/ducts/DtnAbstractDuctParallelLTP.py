import abc
from .DtnAbstractDuct import DtnAbstractDuct
from simulator.utils.DtnUtils import load_class_dynamically

class DtnAbstractDuctParallelLTP(DtnAbstractDuct, metaclass=abc.ABCMeta):
    """ Abstract Parallel LTP. It is subclassed by both DtnOutductParalleLTP
        and DtnInductParallelLTP. When it is initialized, it creates a set of
        LTP ducts and readies them for transmission.

        This class also re-implements the duct's ``success_manager`` and
        ``fail_manager`` since, if an LTP session is cancelled, a bundle should
        not go immediately to the node's limbo (the other LTP session could deliver it).
        Therefore, we need to keep track to how many LTP sessions have succeeded
        and failed.
    """
    def __init__(self, env, name, parent, neighbor):
        # Call parent constructor
        super(DtnAbstractDuctParallelLTP, self).__init__(env, name, parent, neighbor)

        # Initialize variables
        self.nid = parent.nid       # Node id

        # Engines available in this duct
        self.num_engines = 0
        self.engines     = {}

        # Stores the status of the tx for a given bundle
        self.status = {}

    def initialize(self, peer, *args, engines=None, **kwargs):
        """ Initialize multiple LTP engines to be used by in parallel when sending a
            bundle.
        """
        # Call parent initialization
        super(DtnAbstractDuctParallelLTP, self).initialize(peer, **kwargs)

        # If no engines defined, raise error
        if not engines:
            raise ValueError('No engines defined for ParallelLTP duct')

        # Initialize variables
        self.num_engines = len(engines)

        # Iterate over the engines and initialize them
        for engine_id, engine_name in engines.items():
            # Get the engine properties
            props = self.env.config[engine_name]

            # Initialize variables
            iduct, oduct = None, None

            # Create the induct and outduct
            for class_name in getattr(props, 'class'):
                # Load class type
                try:
                    clazz = load_class_dynamically('simulator.ducts.inducts', class_name)
                except ModuleNotFoundError:
                    clazz = load_class_dynamically('simulator.ducts.outducts', class_name)

                # Construct depending on whether is an induct or outduct
                if clazz.duct_type == None:
                    raise RuntimeError(f'{clazz} has no duct_type defined. Is it an induct or outduct?')
                elif clazz.duct_type == 'outduct':
                    oduct = clazz(self.env, engine_id, self, self.neighbor)
                elif clazz.duct_type == 'induct':
                    iduct = clazz(self.env, engine_id, peer, self.nid)
                else:
                    raise RuntimeError('f{clazz} has duct_type = {clazz.duct_type}. Valid options are "induct" and '
                                       '"outduct"')

            # If either the ouduct or induct are not set, throw error
            if iduct == None or oduct == None:
                raise RuntimeError('Could not create duct f{duct_id}')

            # Initialize duct parameters. Initialization must happen after creating the ducts
            # since they must point to each other.
            oduct.initialize(iduct, **dict(props))
            iduct.initialize(oduct, **dict(props))

            # Store the engines
            self.engines[engine_id] = {'induct': iduct, 'outduct': oduct}

    @property
    def available_radios(self):
        """ Return available radios in the DTN node """
        return self.parent.available_radios

    def total_datarate(self, dest):
        return sum(engine['outduct'].total_datarate(dest)
                   for _, engine in self.engines.items())

    @property
    def radios(self):
        """ Only the radios of the outduct engines consume energy.
            This only works because you have an LTP outduct defined
            under the parallel duct. Any other outduct won't work.
        """
        return {eid: engine['outduct'].radios['radio']
                for eid, engine in self.engines.items()}

    def success_manager(self):
        while self.is_alive:
            # Wait for a block that was successfully transmitted
            bundle = yield from self.success_queue.get()

            # Mark success
            self.status[bundle.mid]['success'] += 1

            # Initialize variables
            s = self.status[bundle.mid]['success']
            f = self.status[bundle.mid]['failure']

            # If you have received status from all engines, remove record
            if s + f == self.num_engines: self.status.pop(bundle.mid)

    def radio_error(self, message):
        """ No need to implement it, just use what you have in DtnAbstractDuctLTP
            to cancel the LTP sessions upon error
        """
        pass

    def fail_manager(self):
        """ Re-implement the fail manager. A bundle should only be put in the limbo queue
            if all LTP sessions have failed.
        """
        while self.is_alive:
            # Wait for a block that was not successfully transmitted
            # by an LTP session
            bundle = yield from self.to_limbo.get()

            # Mark failure
            self.status[bundle.mid]['failure'] += 1

            # Initialize variables
            s = self.status[bundle.mid]['success']
            f = self.status[bundle.mid]['failure']

            # If you have gotten status reports from all engines and no success, then put to limbo
            if s == 0 and f == self.num_engines:
                # Get the cid that needs to be excluded. This is not very neat, but
                # essentially reaches into the current DtnNeighborManager for this
                # neighbor and pulls the contact id
                cid = self.parent.queues[self.neighbor].current_cid

                # Send to node's limbo for re-routers
                self.parent.limbo(bundle, cid)

            # If you have received status from all engines, remove record
            if s + f == self.num_engines: self.status.pop(bundle.mid)


