"""Colouring for the code blocks on the documentation pages.

The panels hold three shell sessions and one JSON sample. That is a small
enough surface that a highlighting dependency would outweigh what it buys, and
the blocks are already HTML-escaped in the templates, so they are tokenised
here instead and the result is cached along with the rendered page.

The one rule that matters: a highlighter that changed what a reader copies
would be worse than no highlighter at all. Every token is passed through
verbatim and only wrapped, entities included, which the tests check by
stripping the spans back off and comparing against the input.

Marking up a block is opt-in, through ``<pre data-lang="...">``. The block on
`/start` that a reader pastes into their agent is prose rather than code, and
carries no attribute, so nothing touches it.
"""

import re

ENTITY = r"&(?:#\d+|\w+);"

SHELL = re.compile(
    rf"(?P<c>\#[^\n]*)"
    rf"|(?P<ent>{ENTITY})"
    rf"|(?P<s>\"[^\"\n]*\"|'[^'\n]*')"
    rf"|(?P<v>\$\{{[^}}\n]*\}}|\$\w+)"
    rf"|(?P<assign>[A-Za-z_]\w*(?==))"
    rf"|(?P<f>--?[A-Za-z0-9][\w-]*)"
    rf"|(?P<word>[A-Za-z_][\w./-]*)"
    rf"|(?P<boundary>\$\(|\||\n)"
    rf"|(?P<space>[ \t]+)"
    rf"|(?P<rest>.)",
    re.DOTALL,
)

JSON = re.compile(
    rf"(?P<ent>{ENTITY})"
    rf"|(?P<k>\"[^\"\n]*\"(?=\s*:))"
    rf"|(?P<s>\"[^\"\n]*\")"
    rf"|(?P<lit>\b(?:true|false|null)\b)"
    rf"|(?P<p>[{{}}\[\],:])"
    rf"|(?P<rest>.)",
    re.DOTALL,
)


def _wrap(css: str | None, text: str) -> str:
    return f'<span class="{css}">{text}</span>' if css else text


def _shell(code: str) -> str:
    """Mark up a shell session.

    Which word is the command is a question of position, not spelling, so the
    scan carries one bit of state: whether what comes next starts a command.
    A newline, a pipe, a ``$(`` and an ``&&`` all say it does; whitespace
    leaves it alone, so ``&& cd radius`` still finds ``cd``.
    """
    out, expects_command = [], True
    for match in SHELL.finditer(code):
        kind, text = match.lastgroup, match.group()
        if kind == "word":
            css, expects_command = ("k" if expects_command else None), False
        elif kind == "assign":
            css, expects_command = "v", False
        elif kind == "boundary":
            css, expects_command = None, True
        elif kind == "ent":
            css, expects_command = None, expects_command or text == "&amp;"
        elif kind == "space":
            css = None
        elif kind == "rest":
            css, expects_command = None, False
        else:
            css, expects_command = kind, False
        out.append(_wrap(css, text))
    return "".join(out)


def _json(code: str) -> str:
    return "".join(
        _wrap(None if match.lastgroup in ("ent", "rest") else match.lastgroup,
              match.group())
        for match in JSON.finditer(code)
    )


LANGUAGES = {"sh": _shell, "json": _json}

BLOCK = re.compile(r'<pre data-lang="(\w+)">(.*?)</pre>', re.DOTALL)


def highlight(html: str) -> str:
    """Colour every ``<pre>`` that named a language, and leave the rest alone."""

    def mark(match: re.Match) -> str:
        language, code = match.group(1), match.group(2)
        if language not in LANGUAGES:
            raise ValueError(f"no highlighter for {language!r}")
        return f"<pre>{LANGUAGES[language](code)}</pre>"

    return BLOCK.sub(mark, html)
