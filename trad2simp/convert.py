"""Traditional ↔ Simplified conversion."""

import opencc

_t2s = None
_s2t = None


def _converters():
    global _t2s, _s2t
    if _t2s is None:
        _t2s = opencc.OpenCC('t2s')
        _s2t = opencc.OpenCC('s2t')
    return _t2s, _s2t


def _change_count(src, dst):
    n = min(len(src), len(dst))
    diffs = sum(1 for i in range(n) if src[i] != dst[i])
    return diffs + abs(len(src) - len(dst))


def flip_script(text):
    """Flip Traditional ↔ Simplified.

    Pure traditional becomes simplified, pure simplified becomes traditional.
    Mixed text follows whichever direction rewrites more characters.
    Unchanged when there is nothing to convert.
    """
    if not text:
        return text
    t2s, s2t = _converters()
    to_simp = t2s.convert(text)
    to_trad = s2t.convert(text)
    if to_simp == text and to_trad == text:
        return text
    if to_simp == text:
        return to_trad
    if to_trad == text:
        return to_simp
    if _change_count(text, to_simp) >= _change_count(text, to_trad):
        return to_simp
    return to_trad
