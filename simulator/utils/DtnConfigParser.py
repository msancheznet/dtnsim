from pathlib import Path
import warnings
import yaml
import simulator.parsers as vv
from pydantic import ValidationError

def custom_formatwarning(msg, *args, **kwargs):
    # ignore everything except the message
    return str(msg) + '\n'
warnings.formatwarning = custom_formatwarning

def load_configuration_file(file):
    # If no file, then skip. This must be a validation
    if not file: return

    # Create a Python path object
    path = Path(file)

    # if path does not exist, throw error
    if not path.exists():
        raise FileNotFoundError(f'{path.absolute()} not found')

    # If this is not a .yaml file, throw error
    if path.suffix not in ('.yaml', '.yml'):
        raise ValueError(f'{path.absolute()} is not a YAML file')

    # Read the file
    with path.open(mode='r') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        config['globals']['config_file'] = path.name

    # Return configuration
    return config

def parse_configuration_file(file):
    # Load configuration
    config = load_configuration_file(file)

    # Check all validity of sections and apply default values
    return parse_configuration_dict(config)

def parse_configuration_dict(d, as_dict=False):
    # Initialize variables
    val_d = {}

    # "Tag" and "params" are reserved keywords, they should not be
    # used as YAML tags
    if 'tag' in d:
        raise ValueError('The YAML file cannot contain a tag named "tag"')
    if 'params' in d:
        raise ValueError('The YAML file cannot contain a tag named "params"')

    # Validate the entire configuration file structure
    try:
        vv.DtnConfigFileParser(tag='', params=d, **d)
    except ValidationError as e:
        raise tag_exception(e)

    # Apply validation for globals
    for tag, data in d.items():
        # Get the validator
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            parser = _find_parser(tag, data)

        # Reports are specified as a list. Handle them separately
        if tag == 'reports':
            data = {'reports': data}

        # Apply the validation
        try:
            val_d[tag] = parser(tag=tag, params=d, **data)
        except ValidationError as e:
            raise tag_exception(e, tag)
        except:
            raise

    # Return the parsed data
    return val_d

def _find_parser(tag, data):
    # First, if there is parser explicitly defined, then use it
    try:
        return eval(f'vv.{data["parser"]}')
    except:
        pass

    # Second, see if there is a parser defined for that class
    try:
        return eval(f'vv.{data["class"]}Parser')
    except:
        pass

    # Third, see if there is parser defined for that YAML tag
    try:
        return eval(f'vv.Dtn{tag.capitalize()}Parser')
    except:
        pass

    # Show warning
    warnings.warn(f'Tag "{tag}" cannot be validated. Please define a parser'
                  f' or ``DtnNullParser`` will be used by default.')

    # Return null validator
    return vv.DtnNullParser

def tag_exception(e, tag=None):
    for err in e.errors():
        if tag:
            err['loc'] = (f'YAML tag: "{tag}"', f'Property: "{err["loc"][0]}"')
        else:
            err['loc'] = (f'Tag "{err["loc"][0]}" is missing from YAML file.')
    return e
