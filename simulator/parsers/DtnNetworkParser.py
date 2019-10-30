from copy import deepcopy
from .DtnAbstractParser import DtnAbstractParser
from simulator.utils.math_utils import combvec
from pydantic import BaseModel, validator
from typing import Optional

class DtnNetworkParser(DtnAbstractParser):
    """ Parser for tag ``network`` in YAML configuration file
        It also takes care of replicating nodes if needed.
        It also takes care of creating all-to-all connections if needed.
    """
    # Set of nodes to use
    nodes: Optional[dict]

    # Constellation to use
    constellation: Optional[dict]

    # Set of connections to use
    connections: dict

    @validator('nodes')
    def validate_nodes(cls, nodes, *, values, config, field):
        # Initialize variables
        val_nodes = {}

        # Iterate over nodes and see validate their definition
        for nid, node_def in nodes.items():
            # Validate node definition
            node_def = DtnNetworkNodeValidator(params=values['params'], **node_def)

            # If you only want one 1 copy, you are done
            if node_def.repeat == 1:
                val_nodes[nid] = node_def
                continue

            # Replicate nodes as needed
            for i in range(node_def.repeat):
                # Create a copy of this definition
                new_def        = deepcopy(node_def)
                new_def.alias  = node_def.alias + str(i)
                new_def.repeat = 1

                # Save this node
                val_nodes[nid + str(i)] = new_def

        return val_nodes

    @validator('constellation')
    def validate_constellation(cls, constellation, *, values, config, field):
        if not constellation: return

        # Initialize variables
        val_nodes = {}

        # Validate the constellation definition
        cons_def = DtnConstellationValidator(params=values['params'], **constellation)

        # Validate the node definition
        node_def = DtnNetworkNodeValidator(params=values['params'], **constellation['node'])

        # Build the constellation
        for i in range(1, cons_def.num_planes+1):
            for j in range(1, cons_def.num_sat+1):
                # Create a copy of this definition
                new_def        = deepcopy(node_def)
                new_def.alias  = f'{node_def.alias}{i}{j}'

                # Save this node
                val_nodes[f'{node_def.alias}{i}{j}'] = new_def

        # Save the nodes (Hacky way to do it since Pydantic would put it inside the
        # the ``constellation`` tag and we don't want that).
        values['nodes'] = val_nodes

        # Return the node definition
        return node_def

    @validator('connections')
    def validate_connections(cls, connections, *, values, config, field):
        # Initialize variables
        val_cons = {}
        nodes    = list(values['nodes'].keys())

        # Iterate over connections
        for cid, con_def in connections.items():
            # Validate the connection definition
            con_def = DtnNetworkConnValidator(params=values['params'], **con_def)

            # If connection has origin and destination, this is point-to-point
            if con_def.origin and con_def.destination:
                val_cons[cid] = con_def

            # If connection has neither origin nor destination, then it is a
            # like all-to-all broadcast. Create all necessary connections
            if not con_def.origin and not con_def.destination:
                for o, d in combvec(nodes, nodes):
                    # Skip connection from you to yourself
                    if o == d: continue

                    # Create a copy of this definition
                    new_def             = deepcopy(con_def)
                    new_def.origin      = o
                    new_def.destination = d

                    # Save this connection
                    val_cons[f'broadcast_{o}_{d}'] = new_def

            # If connection has origin but no destination, then it is like
            # one-to-many broadcast
            if con_def.origin and not con_def.destination:
                raise NotImplementedError('This option is currently not allowed')

            # If connection has no origin but a destination, then it is like
            # many-to-one broadcast
            if not con_def.origin and con_def.destination:
                raise NotImplementedError('This option is currently not allowed')

        return val_cons

class DtnNetworkNodeValidator(DtnAbstractParser):
    """ Validator for a node in the ``network`` tag """
    # Node type
    type: str

    # Node alias
    alias: str = ''

    # Number of nodes of this type that you want
    repeat: int = 1

    @validator('type')
    def type_validator(cls, type, *, values, config, field):
        """ Check that this node type is defined """
        return DtnNetworkNodeValidator._validate_tag_exitance(cls, type, values)

class DtnConstellationValidator(DtnAbstractParser):
    """ Validator for a constellation in the ``network`` tag """
    # Node type
    node: dict

    # Number of satellites per constellation plane
    num_sat: int = 1

    # Number of planes
    num_planes: int = 1

class DtnNetworkConnValidator(DtnAbstractParser):
    """ Validator for a connection in the ``network`` tag """
    # Connection type
    type: str

    # Connection origin
    origin: str = None

    # Connection end
    destination: str = None

    @validator('type')
    def type_validator(cls, type, *, values, config, field):
        """ Check that this node type is defined """
        return DtnNetworkNodeValidator._validate_tag_exitance(cls, type, values)
