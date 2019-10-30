import numpy as np
import sys

# ============================================================================================================
# === HELPER FUNCTIONS
# ============================================================================================================

# Check numpy version. Prior to v1.13.0 no numpy.isin was available
np_ver = [int(x) for x in np.version.version.split('.')]
if np_ver[0] <= 1 and np_ver[1] < 13:
    isin = lambda l, vals: np.array([v in vals for v in l])
else:
    isin = np.isin

# Check Python version. All strings in Py3 are unicode
if sys.version_info < (3, 0): str_type = basestring
else: str_type = str