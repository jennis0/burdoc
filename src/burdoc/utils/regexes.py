"""Common place to put regexes that may be reused throughout the processor"""

import re

def get_list_regex() -> re.Pattern:
    """Regex to identify strings that are part of lists. Looks for bullet points,
    alphanumeric brackets (a),(1),a),1), alphanumeric dots, a., 1., and roman numerals

    Returns:
        re.Pattern: A compiled regex pattern
    """
    bullets = "(\u2022)"
    atoz    = "\\(?([a-z])[\\.\\)]"
    num     = "\\(?([0-9]+)[\\.\\)]"
    roman   = "\\(?([ivxIVX]+)[\\)\\.]"
    return re.compile(
        "|".join([bullets, atoz, num, roman]),
        re.UNICODE
    )