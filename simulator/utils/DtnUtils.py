import importlib
import pandas as pd
import random
import sys

# ============================================================================================================
# === MISCELLANEOUS HELPER FUNCTIONS
# ============================================================================================================

def load_class_dynamically(class_package, module_name, class_name=None):
    """ Load a class dynamically.

        :param str class_package: The entire class package (e.g. ``simulator.utils``)
        :param str module_name: The module name (e.g. ``DtnUtils``)
        :param str class_name: The class name. If not provided, assumes same as module_name

        ..code::

            clazz  = find_class_dynamically('simulator.core', 'DtnCore', 'Simulable')
            bundle = clazz(*args, **kwargs)

        Bundle is now an instance of the class simulator.core.DtnCore.Bundle
    """
    if not class_name: class_name = module_name
    module = importlib.import_module(f'{class_package}.{module_name}')
    clazz  = getattr(module, class_name)

    return clazz

def isstring(s):
    return isinstance(s, str)

def shift_traffic(traffic, t_ini):
    # If t_ini is None, no need to shift
    if t_ini is None:
        return traffic

    # Find the min time for the generators file
    t_ini = pd.Timestamp(t_ini)
    t_min =  min(f['StartTime'] for f in traffic.values()).tz_localize(t_ini.tz)
    dt    = t_ini - t_min
    #assert t_ini >= t_min, 'The start time of the scenario must be >= than the generators min time'

    # Shift everything
    for _, f in traffic.items():
        f['StartTime'] += dt
        f['EndTime']   += dt

    return traffic

def rnd_time(t0, asstring=True, tfmt='%d-%b-%Y %H:%M:%S %Z'):
    """ Return a random date t1 such that t1 \in [t0 ; t0 + 1 year]

        :param str/Timestamp t0: Reference time
        :return str/Timestamp:   Random time
    """
    if isstring(t0): t0 = pd.Timestamp(t0)
    d, h = random.randint(0, 364), random.randint(0, 23)
    m, s = random.randint(0, 59), random.randint(0, 59)
    t_ini = t0 + pd.Timedelta(days=d, hours=h, minutes=m, seconds=s)
    if asstring == True: t_ini = t_ini.strftime(tfmt)
    return t_ini

def shift_scenario(t_ini, ts_scenario, te_scenario, tfmt='%d-%b-%Y %H:%M:%S %Z'):
    # Initialize variables
    if isstring(t_ini):       t_ini       = pd.Timestamp(t_ini)
    if isstring(ts_scenario): ts_scenario = pd.Timestamp(ts_scenario)
    if isstring(te_scenario): te_scenario = pd.Timestamp(te_scenario)

    # If t_ini is None, no need to shift
    if t_ini is None:
        t_ini, t_end = ts_scenario, te_scenario
    else:
        # Compute the end time of this scenario
        t_ini = pd.Timestamp(t_ini)
        t_end = (t_ini + (te_scenario - ts_scenario))

    # Compute the EzMonte start and end times
    ts_orbit = (t_ini - pd.Timedelta(days=0.5)).strftime(tfmt)
    te_orbit = (t_end + pd.Timedelta(days=0.5)).strftime(tfmt)

    return t_ini.strftime(tfmt), t_end.strftime(tfmt), ts_orbit, te_orbit