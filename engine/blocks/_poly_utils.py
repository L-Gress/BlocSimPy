"""Shared polynomial coefficient parsing / unicode formatting, used by
TransferFunction (continuous, H(s)) and DiscreteTransferFunction (discrete,
H(z)) so both variants share one implementation instead of duplicating it.
"""


def parse_coeffs(val):
    """Accepts a list/tuple of numbers, or a comma-separated string, and
    returns a list of floats. A bare scalar is wrapped in a 1-element list."""
    if isinstance(val, (list, tuple)):
        return [float(x) for x in val]
    if isinstance(val, str):
        parts = [s.strip() for s in val.split(',') if s.strip()]
        return [float(x) for x in parts]
    return [float(val)]


def to_superscript(num):
    """Converts integer numbers to unicode superscript (e.g., 2 -> ²)."""
    mapping = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(num).translate(mapping)


def format_poly(coeffs, variable="s"):
    """Turn [1, 2, 3] into 's² + 2s + 3' (or with variable='z', 'z² + 2z + 3') using unicode."""
    coeffs = list(coeffs)
    if not coeffs:
        return "0"

    # Remove leading zeros
    while len(coeffs) > 1 and coeffs[0] == 0:
        coeffs.pop(0)

    order = len(coeffs) - 1
    terms = []

    for i, c in enumerate(coeffs):
        power = order - i
        if c == 0:
            continue

        # 1. Handle Sign
        sign = ""
        if c < 0:
            sign = "- "
        elif i > 0:
            sign = "+ "

        abs_c = abs(c)

        # 2. Handle Coefficient (hide 1.0 if part of a term like 1s)
        str_c = f"{abs_c:g}"
        if abs_c == 1 and power > 0:
            str_c = ""

        # 3. Handle Variable
        str_v = ""
        if power == 1:
            str_v = variable
        elif power > 1:
            str_v = f"{variable}{to_superscript(power)}"

        # Edge case: Constant 1
        if str_c == "" and str_v == "":
            str_c = "1"

        terms.append(f"{sign}{str_c}{str_v}")

    result = "".join(terms)
    # Clean up leading "+ " if it exists
    if result.startswith("+ "):
        result = result[2:]
    return result if result else "0"


def format_fraction_label(num_coeffs, den_coeffs, variable="s"):
    """Build a 3-line ASCII fraction label: numerator / bar / denominator."""
    n_str = format_poly(num_coeffs, variable)
    d_str = format_poly(den_coeffs, variable)

    width = max(len(n_str), len(d_str))
    n_pad = n_str.center(width)
    d_pad = d_str.center(width)
    bar = "—" * width

    return f"{n_pad}\n{bar}\n{d_pad}"
