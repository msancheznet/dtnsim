from simulator.ducts.DtnAbstractDuctParallelLTP import DtnAbstractDuctParallelLTP

class DtnOutductParallelLTP(DtnAbstractDuctParallelLTP):
    """ This outduct receives a bundle and sends it through multiple
        LTP session simultaneously.
    """
    duct_type = 'outduct'

    def run(self):
        """ When a bundle is to be sent, replicate it through all concurrent LTP sessions
            being managed. Also, create a status report to know how many sessions have
            succeeded/failed in sending this bundle.
        """
        while self.is_alive:
            # Wait until there is something to transmit
            bundle = yield from self.in_queue.get()

            # Assume for now that both have failed
            self.status[bundle.mid] = {'success': 0, 'failure': 0}

            # Send through all engines. For now, do not copy the bundle.
            for engine in self.engines.values(): engine['outduct'].send(bundle)
