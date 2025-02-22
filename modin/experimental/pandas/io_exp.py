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

"""Implement experimental I/O public API."""

import inspect
import pathlib
import pickle
from typing import Union, IO, AnyStr, Callable, Optional

import pandas
import pandas._libs.lib as lib
from pandas._typing import CompressionOptions, FilePathOrBuffer, StorageOptions

from . import DataFrame
from modin.config import IsExperimental, Engine
from modin.data_management.factories.dispatcher import FactoryDispatcher
from ...pandas import _update_engine


def read_sql(
    sql,
    con,
    index_col=None,
    coerce_float=True,
    params=None,
    parse_dates=None,
    columns=None,
    chunksize=None,
    partition_column: Optional[str] = None,
    lower_bound: Optional[int] = None,
    upper_bound: Optional[int] = None,
    max_sessions: Optional[int] = None,
) -> DataFrame:
    """
    General documentation is available in `modin.pandas.read_sql`.

    This experimental feature provides distributed reading from a sql file.

    Parameters
    ----------
    sql : str or SQLAlchemy Selectable (select or text object)
        SQL query to be executed or a table name.
    con : SQLAlchemy connectable, str, or sqlite3 connection
        Using SQLAlchemy makes it possible to use any DB supported by that
        library. If a DBAPI2 object, only sqlite3 is supported. The user is responsible
        for engine disposal and connection closure for the SQLAlchemy
        connectable; str connections are closed automatically. See
        `here <https://docs.sqlalchemy.org/en/13/core/connections.html>`_.
    index_col : str or list of str, optional
        Column(s) to set as index(MultiIndex).
    coerce_float : bool, default: True
        Attempts to convert values of non-string, non-numeric objects (like
        decimal.Decimal) to floating point, useful for SQL result sets.
    params : list, tuple or dict, optional
        List of parameters to pass to execute method. The syntax used to pass
        parameters is database driver dependent. Check your database driver
        documentation for which of the five syntax styles, described in PEP 249's
        paramstyle, is supported. Eg. for psycopg2, uses %(name)s so use params=
        {'name' : 'value'}.
    parse_dates : list or dict, optional
        - List of column names to parse as dates.
        - Dict of ``{column_name: format string}`` where format string is
          strftime compatible in case of parsing string times, or is one of
          (D, s, ns, ms, us) in case of parsing integer timestamps.
        - Dict of ``{column_name: arg dict}``, where the arg dict corresponds
          to the keyword arguments of :func:`pandas.to_datetime`
          Especially useful with databases without native Datetime support,
          such as SQLite.
    columns : list, optional
        List of column names to select from SQL table (only used when reading
        a table).
    chunksize : int, optional
        If specified, return an iterator where `chunksize` is the
        number of rows to include in each chunk.
    partition_column : str, optional
        Column used to share the data between the workers (MUST be a INTEGER column).
    lower_bound : int, optional
        The minimum value to be requested from the partition_column.
    upper_bound : int, optional
        The maximum value to be requested from the partition_column.
    max_sessions : int, optional
        The maximum number of simultaneous connections allowed to use.

    Returns
    -------
    modin.DataFrame
    """
    Engine.subscribe(_update_engine)
    assert IsExperimental.get(), "This only works in experimental mode"
    _, _, _, kwargs = inspect.getargvalues(inspect.currentframe())
    return DataFrame(query_compiler=FactoryDispatcher.read_sql(**kwargs))


# CSV and table
def _make_parser_func(sep: str) -> Callable:
    """
    Create a parser function from the given sep.

    Parameters
    ----------
    sep : str
        The separator default to use for the parser.

    Returns
    -------
    Callable
    """

    def parser_func(
        filepath_or_buffer: Union[str, pathlib.Path, IO[AnyStr]],
        sep=lib.no_default,
        delimiter=None,
        header="infer",
        names=lib.no_default,
        index_col=None,
        usecols=None,
        squeeze=False,
        prefix=lib.no_default,
        mangle_dupe_cols=True,
        dtype=None,
        engine=None,
        converters=None,
        true_values=None,
        false_values=None,
        skipinitialspace=False,
        skiprows=None,
        nrows=None,
        na_values=None,
        keep_default_na=True,
        na_filter=True,
        verbose=False,
        skip_blank_lines=True,
        parse_dates=False,
        infer_datetime_format=False,
        keep_date_col=False,
        date_parser=None,
        dayfirst=False,
        cache_dates=True,
        iterator=False,
        chunksize=None,
        compression="infer",
        thousands=None,
        decimal: str = ".",
        lineterminator=None,
        quotechar='"',
        quoting=0,
        escapechar=None,
        comment=None,
        encoding=None,
        encoding_errors="strict",
        dialect=None,
        error_bad_lines=None,
        warn_bad_lines=None,
        on_bad_lines=None,
        skipfooter=0,
        doublequote=True,
        delim_whitespace=False,
        low_memory=True,
        memory_map=False,
        float_precision=None,
        storage_options: StorageOptions = None,
    ) -> DataFrame:
        # ISSUE #2408: parse parameter shared with pandas read_csv and read_table and update with provided args
        _pd_read_csv_signature = {
            val.name for val in inspect.signature(pandas.read_csv).parameters.values()
        }
        _, _, _, f_locals = inspect.getargvalues(inspect.currentframe())
        if f_locals.get("sep", sep) is False:
            f_locals["sep"] = "\t"

        kwargs = {k: v for k, v in f_locals.items() if k in _pd_read_csv_signature}
        return _read(**kwargs)

    parser_func.__doc__ = _read.__doc__
    return parser_func


def _read(**kwargs) -> DataFrame:
    """
    General documentation is available in `modin.pandas.read_csv`.

    This experimental feature provides parallel reading from multiple csv files which are
    defined by glob pattern. Works for local files only!

    Parameters
    ----------
    **kwargs : dict
        Keyword arguments in `modin.pandas.read_csv`.

    Returns
    -------
    modin.DataFrame
    """
    Engine.subscribe(_update_engine)

    try:
        pd_obj = FactoryDispatcher.read_csv_glob(**kwargs)
    except AttributeError:
        raise AttributeError("read_csv_glob() is only implemented for pandas on Ray.")

    # This happens when `read_csv` returns a TextFileReader object for iterating through
    if isinstance(pd_obj, pandas.io.parsers.TextFileReader):
        reader = pd_obj.read
        pd_obj.read = lambda *args, **kwargs: DataFrame(
            query_compiler=reader(*args, **kwargs)
        )
        return pd_obj

    return DataFrame(query_compiler=pd_obj)


read_csv_glob = _make_parser_func(sep=",")


def read_pickle_distributed(
    filepath_or_buffer: FilePathOrBuffer,
    compression: Optional[str] = "infer",
    storage_options: StorageOptions = None,
):
    """
    Load pickled pandas object from files.

    In experimental mode, we can use `*` in the filename. The files must contain
    parts of one dataframe, which can be obtained, for example, by
    `to_pickle_distributed` function.
    Note: the number of partitions is equal to the number of input files.

    Parameters
    ----------
    filepath_or_buffer : str, path object or file-like object
        File path, URL, or buffer where the pickled object will be loaded from.
        Accept URL. URL is not limited to S3 and GCS.
    compression : {{'infer', 'gzip', 'bz2', 'zip', 'xz', None}}, default: 'infer'
        If 'infer' and 'path_or_url' is path-like, then detect compression from
        the following extensions: '.gz', '.bz2', '.zip', or '.xz' (otherwise no
        compression) If 'infer' and 'path_or_url' is not path-like, then use
        None (= no decompression).
    storage_options : dict, optional
        Extra options that make sense for a particular storage connection, e.g.
        host, port, username, password, etc., if using a URL that will be parsed by
        fsspec, e.g., starting "s3://", "gcs://". An error will be raised if providing
        this argument with a non-fsspec URL. See the fsspec and backend storage
        implementation docs for the set of allowed keys and values.

    Returns
    -------
    unpickled : same type as object stored in file
    """
    Engine.subscribe(_update_engine)
    assert IsExperimental.get(), "This only works in experimental mode"
    _, _, _, kwargs = inspect.getargvalues(inspect.currentframe())
    return DataFrame(query_compiler=FactoryDispatcher.read_pickle_distributed(**kwargs))


def to_pickle_distributed(
    self,
    filepath_or_buffer: FilePathOrBuffer,
    compression: CompressionOptions = "infer",
    protocol: int = pickle.HIGHEST_PROTOCOL,
    storage_options: StorageOptions = None,
):
    """
    Pickle (serialize) object to file.

    If `*` in the filename all partitions are written to their own separate file,
    otherwise default pandas implementation is used.

    Parameters
    ----------
    filepath_or_buffer : str, path object or file-like object
        File path where the pickled object will be stored.
    compression : {{'infer', 'gzip', 'bz2', 'zip', 'xz', None}}, default: 'infer'
        A string representing the compression to use in the output file. By
        default, infers from the file extension in specified path.
        Compression mode may be any of the following possible
        values: {{'infer', 'gzip', 'bz2', 'zip', 'xz', None}}. If compression
        mode is 'infer' and path_or_buf is path-like, then detect
        compression mode from the following extensions:
        '.gz', '.bz2', '.zip' or '.xz'. (otherwise no compression).
        If dict given and mode is 'zip' or inferred as 'zip', other entries
        passed as additional compression options.
    protocol : int, default: pickle.HIGHEST_PROTOCOL
        Int which indicates which protocol should be used by the pickler,
        default HIGHEST_PROTOCOL (see [1]_ paragraph 12.1.2). The possible
        values are 0, 1, 2, 3, 4, 5. A negative value for the protocol
        parameter is equivalent to setting its value to HIGHEST_PROTOCOL.
        .. [1] https://docs.python.org/3/library/pickle.html.
    storage_options : dict, optional
        Extra options that make sense for a particular storage connection, e.g.
        host, port, username, password, etc., if using a URL that will be parsed by
        fsspec, e.g., starting "s3://", "gcs://". An error will be raised if providing
        this argument with a non-fsspec URL. See the fsspec and backend storage
        implementation docs for the set of allowed keys and values.
    """
    from modin.data_management.factories.dispatcher import FactoryDispatcher

    obj = self
    Engine.subscribe(_update_engine)
    if isinstance(self, DataFrame):
        obj = self._query_compiler
    FactoryDispatcher.to_pickle_distributed(
        obj,
        filepath_or_buffer=filepath_or_buffer,
        compression=compression,
        protocol=protocol,
        storage_options=storage_options,
    )
