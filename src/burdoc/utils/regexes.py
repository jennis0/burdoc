"""Common place to put regexes that may be reused throughout the processor"""

import re

def get_list_regex() -> re.Pattern:
    """Regex to identify strings that are part of lists. Looks for bullet points,
    alphanumeric brackets (a),(1),a),1), and alphanumeric dots, a., 1.

    Returns:
        re.Pattern: A compiled regex pattern
    """
    
    return re.compile(
        "(?:(\u2022)|\(?([a-z])\)\.?|\(?([0-9]+)\)\.?|([0-9]+)\.)",  
        re.UNICODE
    )