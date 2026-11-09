#src/utils/validation.py
"""
DataFrame validation utilities.

Provides functions to validate that DataFrames contain expected
columns before processing, preventing runtime errors.
"""
from typing import List
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def validate_dataframe_columns(
    df: pd.DataFrame, 
    required_columns: List[str], 
    context: str = "DataFrame") -> None:
    """
    Validate that DataFrame contains all required columns.
    
    Args:
        df: DataFrame to validate
        required_columns: List of column names that must be present
        context: Description of where/why validation is happening (for error messages)
        
    Raises:
        ValueError: If any required columns are missing
    """
    if df.empty:
        logger.debug(f"{context} is empty - skipping column validation")
        return
    
    missing_columns = set(required_columns) - set(df.columns)
    
    if missing_columns:
        available = ", ".join(df.columns)
        missing = ", ".join(sorted(missing_columns))
        error_msg = (
            f"{context} missing required columns: {missing}. "
            f"Available columns: {available}. "
            f"Check SQL query returns all expected columns."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.debug(f"{context} validation passed - all {len(required_columns)} required columns present")
