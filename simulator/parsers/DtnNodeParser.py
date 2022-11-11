from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator
from typing import Any, Dict, List, Optional

class DtnNodeParser(DtnAbstractParser):
    """ Parser for DtnNode's YAML configuration parameters """
    # Router type. It must be tag of an element defined in the YAML
    router: str

    # List of generators. Each generator must be a tag in the YAML file
    generators: Optional[List[str]]

    # Outduct selector. It must be a tag in the YAML file
    selector: str

    # List of radios this node carries. Each radio must be a tag in the
    # YAML file
    radios: List[str]

    # Mobility model. If provided, it is because the router needs contact
    # plan data to do its job
    mobility_model: str

    # Endpoints. Equivalent to ports in TCP/IP. It allows you to address
    # a specific part of a node by the EID
    endpoints: Dict[Any, str] = {0: 'DtnDefaultEndpoint'}

    # Time to wait between consecutive limbo pulls in [sec]. If limbo_wait is
    # infinite (default), then you only pull from the limbo when there is something
    # there waiting to be re-routed.
    limbo_wait: float = float('inf')

    @validator('router')
    def validate_router(cls, router, *, values, **kwargs):
        return DtnNodeParser._validate_tag_exitance(cls, router, values)

    @validator('generators')
    def validate_generators(cls, generator, *, values, **kwargs):
        return DtnNodeParser._validate_tag_exitance(cls, generator, values)

    @validator('selector')
    def validate_selector(cls, selector, *, values, **kwargs):
        return DtnNodeParser._validate_tag_exitance(cls, selector, values)

    @validator('radios')
    def validate_radios(cls, radio, *, values, **kwargs):
        return DtnNodeParser._validate_tag_exitance(cls, radio, values)

    @validator('mobility_model')
    def validate_mobility_model(cls, mobility_model, *, values, **kwargs):
        return DtnNodeParser._validate_tag_exitance(cls, mobility_model, values)

    @validator('endpoints', whole=True)
    def validate_endpoints(cls, endpoints, *, values, **kwargs):
        # When validating a dictionary, Pydantic first gives you the keys and
        # values to validate individually. This is currently a known Pydantic
        # bug (see Pydantic github, issue #254)
        if not isinstance(endpoints, dict):
            return endpoints

        # Add default endpoint with the default EID. If the user had specified
        # something else in the 0 EID, it will be overriden
        endpoints[0] = 'DtnDefaultEndpoint'

        return endpoints


        #
