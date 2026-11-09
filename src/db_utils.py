# src/db_utils.py
import os
from decouple import config
from contextlib import contextmanager
from sshtunnel import SSHTunnelForwarder
from sqlalchemy import create_engine, text
import pandas as pd
from pathlib import Path
import re

# Load .env
SSH_HOST = config('SSH_HOST', default=None)
SSH_PORT = config('SSH_PORT', default=22, cast=int)
SSH_USER = config('SSH_USER', default='prominence')
SSH_KEY_PATH = os.path.expanduser(config('SSH_KEY_PATH', default=''))

DB_HOST = config('DB_HOST')
DB_PORT = config('DB_PORT', cast=int)
DB_NAME = config('DB_NAME')
DB_USER = config('DB_USER')
DB_PASS = config('DB_PASS')

USE_SSH_TUNNEL = config('USE_SSH_TUNNEL', default=False, cast=bool)


def validate_query_file(query_path: Path) -> str:
    """
    Safely load and validate SQL query from file.

    This function performs security checks to ensure only valid SQL files
    are loaded from the filesystem. It validates file existence and extension
    before reading the contents.

    Parameters
    ----------
    query_path : Path
        Path object pointing to the SQL query file. Must have a .sql extension.

    Returns
    -------
    str
        The contents of the SQL file as a string.

    Raises
    ------
    FileNotFoundError
        If the specified query file does not exist at the given path.
    ValueError
        If the file does not have a .sql extension.

    Examples
    --------
    >>> from pathlib import Path
    >>> query = validate_query_file(Path('queries/select_users.sql'))
    >>> print(query)
    'SELECT * FROM users;'

    Notes
    -----
    This function is designed as a security measure to prevent arbitrary
    file reads and ensure only SQL files are processed.
    """
    if not query_path.exists():
       raise FileNotFoundError(f"Query file not found: {query_path}")

    if query_path.suffix != '.sql':
       raise ValueError("Only .sql files are allowed")

    with open(query_path, 'r', encoding='utf-8') as f:
       return f.read()


def query_to_df(query: str, display_all: bool=True, local: bool=False) -> pd.DataFrame:
    """
    Execute SQL query and return results as a pandas DataFrame.

    This function supports multiple execution modes: remote PostgreSQL database
    (with optional SSH tunnel), or local DuckDB execution. It also provides
    options for controlling DataFrame display settings.

    Parameters
    ----------
    query : str
        SQL query string to execute. Must be valid SQL for the target database.
    display_all : bool, optional
        If True, configures pandas to display all rows and columns without
        truncation. If False, resets to default display limits. Default is True.
    local : bool, optional
        If True, executes the query using DuckDB locally instead of connecting
        to the remote PostgreSQL database. Default is False.

    Returns
    -------
    pd.DataFrame
        Query results as a pandas DataFrame.

    Raises
    ------
    FileNotFoundError
        If SSH tunnel is enabled but SSH_KEY_PATH does not exist.
    sqlalchemy.exc.DatabaseError
        If there are issues connecting to or querying the database.
    duckdb.Error
        If local=True and there are issues with the DuckDB query execution.

    Examples
    --------
    >>> # Query remote database with SSH tunnel
    >>> df = query_to_df("SELECT * FROM users LIMIT 10")
    >>> 
    >>> # Query local DuckDB database
    >>> df = query_to_df("SELECT * FROM 'data.parquet'", local=True)
    >>>
    >>> # Query without full display
    >>> df = query_to_df("SELECT * FROM users", display_all=False)

    Notes
    -----
    - Connection mode is determined by the USE_SSH_TUNNEL environment variable
    - When USE_SSH_TUNNEL is True, requires valid SSH credentials in environment
    - SSH tunnel automatically closes after query execution via context manager
    - Display options affect the global pandas display settings for the session
    """
    if display_all:
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', None)
    else:
        pd.reset_option('display.max_rows')
        pd.reset_option('display.max_columns')
        pd.reset_option('display.width')
        pd.reset_option('display.max_colwidth')
    if local:
        import duckdb
        df = duckdb.query(query).to_df()
        return df
    if USE_SSH_TUNNEL and SSH_HOST and SSH_KEY_PATH:
        if not os.path.exists(SSH_KEY_PATH):
            raise FileNotFoundError(f'SSH key not found: {SSH_KEY_PATH}')
        with SSHTunnelForwarder(
                (SSH_HOST, SSH_PORT),
                ssh_username=SSH_USER,
                ssh_private_key=SSH_KEY_PATH,
                remote_bind_address=(DB_HOST, DB_PORT)
            ) as tunnel:
            connection_string = (
                    f"postgresql://{DB_USER}:{DB_PASS}@"
                    f"localhost:{tunnel.local_bind_port}/{DB_NAME}"
            )
            engine = create_engine(connection_string)
            return pd.read_sql(query, engine)
    else:
        connection_string = (
                f"postgresql://{DB_USER}:{DB_PASS}@"
                f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        engine = create_engine(connection_string)
        return pd.read_sql(query, engine)

@contextmanager
def get_db_connection():
    """
    Context manager for database connection with optional SSH tunnel.

    Provides a safely managed database connection that automatically handles
    resource cleanup. Supports both direct PostgreSQL connections and connections
    through an SSH tunnel based on environment configuration.

    Yields
    ------
    sqlalchemy.engine.base.Connection
        Active SQLAlchemy database connection object.

    Raises
    ------
    FileNotFoundError
        If USE_SSH_TUNNEL is True but the SSH key file specified in SSH_KEY_PATH
        does not exist.
    sqlalchemy.exc.DatabaseError
        If connection to the database fails.
    sshtunnel.BaseSSHTunnelForwarderError
        If SSH tunnel creation fails.

    Examples
    --------
    >>> with get_db_connection() as conn:
    ...     result = conn.execute(text("SELECT COUNT(*) FROM users"))
    ...     count = result.scalar()
    ...     print(f"Total users: {count}")

    >>> # Connection is automatically closed after the with block
    >>> # No manual cleanup required

    Notes
    -----
    - Connection mode (direct vs SSH tunnel) is controlled by USE_SSH_TUNNEL
      environment variable
    - The connection is automatically closed when exiting the context manager,
      even if an exception occurs
    - SSH tunnel (if used) is also automatically torn down on context exit
    - This is the preferred method for executing multiple queries or transactions
      that need to share a connection
    """
    if USE_SSH_TUNNEL and SSH_HOST:
        if not os.path.exists(SSH_KEY_PATH):
            raise FileNotFoundError(f"SSH key not found: {SSH_KEY_PATH}")
        with SSHTunnelForwarder(
                (SSH_HOST, SSH_PORT),
                ssh_username=SSH_USER,
                ssh_private_key=SSH_KEY_PATH,
                remote_bind_address=(DB_HOST, DB_PORT)
        ) as tunnel:
            connection_string = (
                    f"postgresql://{DB_USER}:{DB_PASS}@"
                    f"localhost:{tunnel.local_bind_port}/{DB_NAME}"
            )
            engine = create_engine(connection_string)
            conn = engine.connect()
            try:
                yield conn
            finally:
                conn.close()
    else:
        connection_string = (
                f"postgresql://{DB_USER}:{DB_PASS}@"
                f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        engine = create_engine(connection_string)
        conn = engine.connect()
        try:
            yield conn
        finally:
            conn.close()


def check_db_connection() -> bool:
    """
    Check if the database connection can be established.

    Performs a simple connectivity test by attempting to establish a connection
    and execute a trivial query (SELECT 1). Useful for health checks and
    debugging connection issues.

    Returns
    -------
    bool
        True if connection is successful and a test query can be executed,
        False if any connection errors occur.

    Examples
    --------
    >>> if check_db_connection():
    ...     print("Database is accessible")
    ...     df = query_to_df("SELECT * FROM users")
    ... else:
    ...     print("Cannot connect to database")
    ...     # Handle offline mode or alert user

    >>> # Use in application startup
    >>> assert check_db_connection(), "Database unavailable at startup"

    Notes
    -----
    - Connection mode (direct vs SSH tunnel) follows the same logic as other
      database functions, controlled by USE_SSH_TUNNEL environment variable
    - All exceptions are caught and logged; the function never raises exceptions
    - The test query (SELECT 1) is lightweight and doesn't access any tables
    - Connection is automatically closed after the test, whether successful or not
    - Error messages are printed to stdout for debugging purposes
    """
    try:
        if USE_SSH_TUNNEL and SSH_HOST and SSH_KEY_PATH:
            if not os.path.exists(SSH_KEY_PATH):
                raise FileNotFoundError(f"SSH key not found: {SSH_KEY_PATH}")
            with SSHTunnelForwarder(
                    (SSH_HOST, SSH_PORT),
                    ssh_username=SSH_USER,
                    ssh_private_key=SSH_KEY_PATH,
                    remote_bind_address=(DB_HOST, DB_PORT)
            ) as tunnel:
                connection_string = (
                        f"postgresql://{DB_USER}:{DB_PASS}@"
                        f"localhost:{tunnel.local_bind_port}/{DB_NAME}"
                )
                engine = create_engine(connection_string)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
        else:
            connection_string = (
                    f"postgresql://{DB_USER}:{DB_PASS}@"
                    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
            )
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

