from .DtnAbstractParser import DtnAbstractParser

class DtnRandomWaypointMobilityModelParser(DtnAbstractParser):
    """ YAML input validator for DtnRandomWaypointMobilityModel """
    # Maximum size of the scenario in the x-axis
    x_max: float

    # Maximum size of the scenario in the y-axis
    y_max: float

    # Maximum speed of a node. Units are consistent with x/y_max and the
    # simulation time units
    v_max: float

    # Minimum speed of a node. Units are consistent with x/y_max and the
    # simulation time units
    v_min: float

    # Maximum wait time of node between going to another target.
    # Units depend on simulation time units
    wait_max: float

    # Minimum wait time of node between going to another target.
    # Units depend on simulation time units
    wait_min: float

    # Time step to use when simulating the position of all nodes
    time_step: int

    # Time until which node mobility is simulated. If simulation duration
    # is longer, them the nodes will be static for the rest of it.
    until: int