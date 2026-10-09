"""Similarity measures for code and prose (cross-candidate and reference-AI matching)."""
import re

_KEYWORDS = set("""
auto break case char const continue default do double else enum extern float for goto if int long register
return short signed sizeof static struct switch typedef union unsigned void volatile while bool true false
class public private protected new delete namespace using template typename std cout cin endl include
def import from as in is not and or None True False lambda yield with try except finally raise pass print
function let var const of console log require return null undefined this
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||[^\s\w]")


def _strip_comments(code):
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)
    code = re.sub(r"//[^\n]*", " ", code)
    code = re.sub(r"#(?!include)[^\n]*", " ", code)
    code = re.sub(r'("""|\'\'\').*?\1', " ", code, flags=re.S)
    return code


def code_tokens(code):
    """Tokenise code and rename identifiers/literals so renaming variables does not hide copying."""
    tokens = []
    for tok in _TOKEN_RE.findall(_strip_comments(code or "")):
        if tok in _KEYWORDS:
            tokens.append(tok)
        elif re.match(r"[A-Za-z_]", tok):
            tokens.append("ID")
        elif tok.isdigit():
            tokens.append("NUM")
        else:
            tokens.append(tok)
    return tokens


def text_tokens(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def shingles(tokens, k):
    if len(tokens) < k:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def code_similarity(code_a, code_b, k=5):
    return jaccard(shingles(code_tokens(code_a), k), shingles(code_tokens(code_b), k))


def text_similarity(text_a, text_b, k=4):
    return jaccard(shingles(text_tokens(text_a), k), shingles(text_tokens(text_b), k))


def contains_canary(answer, canary):
    """True when the distinctive identifier(s) from the canary instruction appear in the answer."""
    if not answer or not canary:
        return False
    markers = [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", canary)
               if "_" in w or any(c.isdigit() for c in w)]
    if not markers:
        return canary.strip().lower() in answer.lower()
    return any(re.search(rf"\b{re.escape(m)}\b", answer) for m in markers)
