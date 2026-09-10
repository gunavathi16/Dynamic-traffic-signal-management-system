"""
Read-Only SQL Safety Layer for AI-Augmented Smart Traffic Signal Management System.
Validates generated queries to ensure strictly non-destructive, read-only analytical execution.
"""

import re
import sqlparse
from sqlparse.sql import Statement, Token
from sqlparse.tokens import DDL, DML, Keyword

class SQLSafetyViolation(Exception):
    """Raised when a query violates read-only safety rules."""
    pass


FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "REPLACE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "SHUTDOWN", "MERGE",
    "UPSERT", "ATTACH", "DETACH", "PRAGMA", "VACUUM", "CALL", "COPY"
}

ALLOWED_STATEMENTS = {"SELECT"}


def validate_and_sanitize_sql(sql_query: str, max_limit: int = 100) -> str:
    """
    Validates that a SQL query is strictly a read-only SELECT statement.
    Appends or clamps a LIMIT clause to prevent unbounded result sets.

    Raises SQLSafetyViolation if destructive keywords or multiple statements are found.
    """
    if not sql_query or not sql_query.strip():
        raise SQLSafetyViolation("SQL query is empty.")

    # Strip markdown code fencing if the LLM provided ```sql ... ```
    cleaned = sql_query.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Parse with sqlparse
    statements = sqlparse.parse(cleaned)
    if not statements:
        raise SQLSafetyViolation("Unable to parse SQL statement.")

    # Reject multiple statements (prevents SELECT 1; DROP TABLE ...)
    # Filter out empty statements resulting from trailing semicolons
    valid_statements = [s for s in statements if str(s).strip() not in (";", "")]
    if len(valid_statements) > 1:
        raise SQLSafetyViolation(
            f"Multiple SQL statements detected ({len(valid_statements)}). Only single SELECT queries are permitted."
        )

    stmt: Statement = valid_statements[0]
    stmt_type = stmt.get_type().upper()

    # Allow WITH (CTE) only if inner statement is SELECT
    if stmt_type == "UNKNOWN" and cleaned.upper().startswith("WITH"):
        # Common Table Expression
        pass
    elif stmt_type not in ALLOWED_STATEMENTS:
        raise SQLSafetyViolation(
            f"Statement type '{stmt_type}' is prohibited. Only read-only SELECT statements are allowed."
        )

    # Token-level deep inspection for forbidden DDL / DML keywords
    tokens = list(stmt.flatten())
    for token in tokens:
        val = token.value.upper()
        if val in FORBIDDEN_KEYWORDS:
            raise SQLSafetyViolation(
                f"Prohibited destructive keyword detected: '{val}'. Write/Schema operations are blocked."
            )

    # Check for SQL injection commentary evasions (-- or /* */ concealing commands)
    for token in stmt.tokens:
        if token.is_whitespace:
            continue
        if token.ttype in (sqlparse.tokens.Comment.Single, sqlparse.tokens.Comment.Multiline):
            comment_text = token.value.upper()
            for kw in FORBIDDEN_KEYWORDS:
                if kw in comment_text:
                    raise SQLSafetyViolation(f"Dangerous keyword '{kw}' found within SQL comment block.")

    # Enforce or verify LIMIT clause
    query_str = cleaned.rstrip(";").strip()
    if not re.search(r"\bLIMIT\s+\d+\b", query_str, re.IGNORECASE):
        # Auto-append LIMIT
        query_str = f"{query_str} LIMIT {max_limit}"
    else:
        # If LIMIT exists, ensure it does not exceed max_limit
        limit_match = re.search(r"\bLIMIT\s+(\d+)\b", query_str, re.IGNORECASE)
        if limit_match:
            limit_val = int(limit_match.group(1))
            if limit_val > max_limit:
                query_str = re.sub(
                    r"\bLIMIT\s+\d+\b", f"LIMIT {max_limit}", query_str, flags=re.IGNORECASE
                )

    return query_str
