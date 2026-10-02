"""JSON that is safe to print inside a page's <script>.

``json.dumps`` output is not: a string holding ``</script>`` ends the script
element wherever it appears, and what follows is read as HTML. The values
here come from documents (a highlight is text selected in a PDF), so they
are not ours to trust. Escaping the three characters HTML cares about as
JSON ``\\uXXXX`` sequences leaves the data unchanged for JavaScript and
inert for the HTML parser. (Django's ``json_script`` filter does the same;
this is for templates that assign the value inside an existing script.)
"""

import json

_SCRIPT_ESCAPES = {
    ord("<"): "\\u003C",
    ord(">"): "\\u003E",
    ord("&"): "\\u0026",
    # Line terminators that are legal in JSON but not in older JavaScript.
    0x2028: "\\u2028",
    0x2029: "\\u2029",
}


def json_for_script(value):
    return json.dumps(value).translate(_SCRIPT_ESCAPES)
