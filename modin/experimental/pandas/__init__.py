# Licensed to Modin Development Team under one or more contributor license agreements.
# See the NOTICE file distributed with this work for additional information regarding
# copyright ownership.  The Modin Development Team licenses this file to you under the
# Apache License, Version 2.0 (the "License"); you may not use this file except in
# compliance with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""
The main module through which interaction with the experimental API takes place.

See `Experimental API Reference` for details.

Notes
-----
* Some of experimental APIs deviate from pandas in order to provide improved
  performance.

* Although the use of experimental backends and engines is available through the
  `modin.pandas` module when defining environment variable `MODIN_EXPERIMENTAL=true`,
  the use of experimental I/O functions is available only through the
  `modin.experimental.pandas` module.

Examples
--------
>>> import modin.experimental.pandas as pd
>>> df = pd.read_csv_glob("data*.csv")
"""

from modin.config import IsExperimental

IsExperimental.put(True)

# import numpy_wrap as early as possible to intercept all "import numpy" statements
# in the user code
from .numpy_wrap import _CAUGHT_NUMPY  # noqa F401
from modin.pandas import *  # noqa F401, F403
from .io_exp import (  # noqa F401
    read_sql,
    read_csv_glob,
    read_pickle_distributed,
    to_pickle_distributed,
)
import warnings

setattr(DataFrame, "to_pickle_distributed", to_pickle_distributed)  # noqa: F405

warnings.warn(
    "Thank you for using the Modin Experimental pandas API."
    "\nPlease note that some of these APIs deviate from pandas in order to "
    "provide improved performance."
)
