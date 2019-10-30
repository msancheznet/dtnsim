from .DtnAbstractConnection import DtnAbstractConnection

class DtnStaticConnection(DtnAbstractConnection):

    def initialize(self, start_connection=True):
        self.prop_delay = self.props.prop_delay
        super().initialize(start_connection=start_connection)

    def set_contact_properties(self):
        ''' Set properties of the current contact '''
        # if no propagation delay available, grab it from the mobility model
        prop_delay = self.props.prop_delay

        if prop_delay == None:
            prop_delay = self.mobility_model.prop_delay

        # Store it
        self.prop_delay = {self.dest.nid: prop_delay}

    def run(self):
        # Open the connection
        self.open_connection()

        # Nothing to do here, just force a generator
        # yield self.env.exit()
        yield self.env.timeout(0)


