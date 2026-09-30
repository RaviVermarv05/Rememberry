"""
Small shared helper, split out of app.py so mode-4's review_routes.py can
reuse it too without importing app.py back (app.py is the entry-point script
- `python webapp/app.py` - so importing it as a module from elsewhere can
re-run the whole file under a second name and crash with a circular import;
that's the only reason this one function lives in its own file).
"""
from flask import jsonify

from messages import Range_message


def check_range(total, start, end):
    """Web version of selected_range() in logics.py: returns (start, end, error).
    Same messages; a start past the last word is rejected, an end past it is cut back."""
    if start is None or end is None:
        return None, None, None
    try:
        start, end = int(start), int(end)
    except (TypeError, ValueError):
        return None, None, (jsonify({"error": Range_message.valid_range}), 400)
    if start < 1 or end < start:
        return None, None, (jsonify({"error": Range_message.invalid_range}), 400)
    if start > total:
        return None, None, (jsonify({"error": Range_message.out_of_range.format(max=total), "max": total}), 400)
    return start, min(end, total), None