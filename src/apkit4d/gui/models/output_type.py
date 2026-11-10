from enum import StrEnum


class OutputType(StrEnum):
    """Enumeration representing the available output data formats.

    Attributes:
        PARQUET: Apache Parquet columnar storage format.
        CSV: Comma-Separated Values plain text format.
    """

    PARQUET = "parquet"
    CSV = "csv"
