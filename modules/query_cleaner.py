import re
import logging
from typing import Dict, Any, Optional


def _fix_common_postgres_array_errors(sql: str) -> str:
    """
    Fix common LLM-generated Postgres mistakes with arrays, especially:
    - Using string_to_array(...) as a table source without unnest(), causing TRIM to see text[]
    - Missing LATERAL when referencing columns from the left side in table functions

    Examples fixed:
    FROM table, LATERAL string_to_array(col, ',') AS x
      -> FROM table, LATERAL unnest(string_to_array(col, ',')) AS x

    CROSS JOIN string_to_array(col, ',') AS x
      -> CROSS JOIN LATERAL unnest(string_to_array(col, ',')) AS x
    """
    fixed = sql

    # 1) LATERAL string_to_array(...) -> LATERAL unnest(string_to_array(...))
    fixed = re.sub(
        r"(\bLATERAL\s+)string_to_array\(([^)]+)\)\s+AS\s+(\w+)",
        r"\1unnest(string_to_array(\2)) AS \3",
        fixed,
        flags=re.IGNORECASE,
    )

    # 2) , string_to_array(...) AS x  -> , LATERAL unnest(string_to_array(...)) AS x
    fixed = re.sub(
        r",\s*string_to_array\(([^)]+)\)\s+AS\s+(\w+)",
        r", LATERAL unnest(string_to_array(\1)) AS \2",
        fixed,
        flags=re.IGNORECASE,
    )

    # 3) CROSS JOIN string_to_array(...) AS x -> CROSS JOIN LATERAL unnest(string_to_array(...)) AS x
    fixed = re.sub(
        r"\bCROSS\s+JOIN\s+string_to_array\(([^)]+)\)\s+AS\s+(\w+)",
        r"CROSS JOIN LATERAL unnest(string_to_array(\1)) AS \2",
        fixed,
        flags=re.IGNORECASE,
    )

    # 4) JOIN LATERAL string_to_array(...) AS x -> JOIN LATERAL unnest(string_to_array(...)) AS x
    fixed = re.sub(
        r"\bJOIN\s+LATERAL\s+string_to_array\(([^)]+)\)\s+AS\s+(\w+)",
        r"JOIN LATERAL unnest(string_to_array(\1)) AS \2",
        fixed,
        flags=re.IGNORECASE,
    )

    return fixed


def clean_sql_query(text: str) -> str:
    # Remove SQL code blocks
    text = re.sub(r"```(?:sql|SQL|SQLQuery|mysql|postgresql)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
    
    # Remove leading labels like "SQL:", "sqlite", "ite", etc.
    text = re.sub(r"^(?:sqlite|ite|SQL\s*Query|SQLQuery|MySQL|PostgreSQL|SQL)\s*:?[\s\\n]*", "", text.strip(), flags=re.IGNORECASE)
    
    # Normalize whitespace first
    text = re.sub(r'\s+', ' ', text.strip())

    # Structural corrections for Postgres array handling
    text = _fix_common_postgres_array_errors(text)

    return text


def normalize_user_query(query: str) -> str:
    """
    Normalize user query by correcting common issues
    """
    if not query:
        return query
    
    # Additional query normalizations
    # Fix common abbreviations
    replacements = {
        'dod': 'do-or-die',
        'd.o.d': 'do-or-die',
        'do or die': 'do-or-die',
        'super tackle': 'super tackle',
        'bonus point': 'bonus point',
        'first half': 'first half',
        'second half': 'second half',
        'period 1': 'first half',
        'period 2': 'second half',
        'playing 7': 'playing 7',
        'playing 11': 'playing 11',
        'playing seven': 'playing 7',
        'playing eleven': 'playing 11',
    }
    
    normalized_query = query
    for old, new in replacements.items():
        normalized_query = re.sub(r'\b' + re.escape(old) + r'\b', new, normalized_query, flags=re.IGNORECASE)
    
    # Map user phrasing to dataset terms to guide the prompt better
    # "raider skill(s)" → "attacking skills"; "defender skill(s)" → "defense skills"
    normalized_query = re.sub(r'raider\s+skills?', 'attacking skills', normalized_query, flags=re.IGNORECASE)
    normalized_query = re.sub(r'(defender|defence|defense)\s+skills?', 'defense skills', normalized_query, flags=re.IGNORECASE)
    
    return normalized_query


def print_sql(x):
    logging.info("User Question: %s", x.get("question", "N/A"))
    logging.info("Cleaned SQL: %s", x.get("query"))
    return x


def enhance_query_with_corrections(question: str, sql_result: str) -> Dict[str, Any]:
    """
    Enhance query results with corrections and suggestions
    """
    corrections = []
    suggestions = []
    
    # Check if the result indicates no data found
    if "did not play" in sql_result.lower() or "no raids" in sql_result.lower():
        suggestions.append("No data found for the specified criteria. Please check your query parameters.")
    
    return {
        "corrections": corrections,
        "suggestions": list(set(suggestions))  # Remove duplicates
    }


# -------------------- Skill normalization utilities --------------------
_SUFFIX_PATTERN = re.compile(r'(On|Under|By|With)[A-Z].*$')
_LOBBYOUT_PATTERN = re.compile(r'\bLobbyOut[A-Za-z]*')


def normalize_skill_name(raw: str) -> Optional[str]:
    """Return base skill name from a raw technique string.
    - Strips trailing context like OnRCV/UnderLIN/ByRCNR/WithLCV.
    - Returns None if the token represents a non-skill like LobbyOut*.
    """
    if not raw:
        return None
    token = raw.strip()
    if _LOBBYOUT_PATTERN.match(token):
        return None
    # Remove trailing context starting with On/Under/By/With followed by uppercase letters
    base = _SUFFIX_PATTERN.sub('', token)
    return base or token


def normalize_skills_in_result(sql_query: str, result_text: str) -> str:
    """Best-effort normalization of skills inside a textual SQL result.
    This is conservative and only touches technique-like tokens.
    """
    if not result_text:
        return result_text
    # Only run when techniques are part of query to avoid unintended changes
    if not re.search(r'"(?:Attack|Defense)_Techniques_Used"', sql_query):
        return result_text
    
    # Replace LobbyOut* tokens with '' (removed)
    cleaned = _LOBBYOUT_PATTERN.sub('', result_text)
    
    # Normalize tokens that look like TechniqueOnXXX/TechniqueUnderXXX/etc.
    def _strip_suffix(m: re.Match) -> str:
        full = m.group(0)
        # Find the split position where suffix starts
        split = _SUFFIX_PATTERN.search(full)
        if split:
            return full[:split.start()]
        return full
    
    # Heuristic: words with camel case followed by On/Under/By/With + caps
    pattern = re.compile(r'[A-Z][a-zA-Z]*(?:[A-Z][a-z]+)*?(?:On|Under|By|With)[A-Z][A-Za-z]*')
    cleaned = pattern.sub(_strip_suffix, cleaned)
    
    # Remove accidental duplicate commas/spaces introduced by deletions
    cleaned = re.sub(r'\s*,\s*,+', ', ', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    return cleaned
