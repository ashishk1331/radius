"""Marking up the code blocks on the documentation pages.

The thing worth guarding is not which token got which colour, it is that a
reader copying a block out of the page gets back exactly what the template
said. Every case below either checks that, or checks that a token a reader
needs to see as distinct is in fact distinguished.
"""

import re

import pytest

from radius.server import web
from radius.server.highlight import highlight

TAGS = re.compile(r"</?span[^>]*>")


def bare(html: str) -> str:
    """The block as a reader would copy it, with the colouring taken back off."""
    return TAGS.sub("", html)


def test_a_block_without_a_language_is_left_alone():
    """The paste-into-your-agent block is prose, and opts out by saying nothing."""
    html = "<pre>Set up radius for me &amp; tell me how it went.</pre>"

    assert highlight(html) == html


def test_an_unknown_language_is_a_mistake_rather_than_a_silent_pass():
    """A typo in the attribute would otherwise ship as an uncoloured block."""
    with pytest.raises(ValueError, match="perl"):
        highlight('<pre data-lang="perl">print 1;</pre>')


def test_the_language_attribute_does_not_reach_the_page():
    assert "data-lang" not in highlight('<pre data-lang="sh">uv sync</pre>')


@pytest.mark.parametrize("language, code", [
    ("sh", "git clone https://example.com/x &amp;&amp; cd x\n"
           "# a comment with an ampersand &amp; a quote\n"
           "TOKEN=$(uv run radius token issue -c app --ttl 60 | tail -2)\n"
           'curl -H "Authorization: Bearer $TOKEN" &lt; in.txt'),
    ("json", '{\n  "data": [{ "id": "1", "n": 2, "ok": true, "x": null }]\n}'),
])
def test_marking_up_a_block_does_not_change_what_it_says(language, code):
    """Including the entities — a doubly escaped &amp; would be a broken command."""
    marked = highlight(f'<pre data-lang="{language}">{code}</pre>')

    assert bare(marked) == f"<pre>{code}</pre>"


def test_a_comment_is_marked_as_one():
    marked = highlight('<pre data-lang="sh">uv sync\n# install</pre>')

    assert '<span class="c"># install</span>' in marked


def test_the_command_is_the_first_word_of_a_line_not_a_known_name():
    """`radius` leads one line and trails another; only the leading one is it."""
    marked = highlight('<pre data-lang="sh">radius serve\nturso db create radius</pre>')

    assert marked.count('<span class="k">radius</span>') == 1
    assert '<span class="k">turso</span>' in marked


@pytest.mark.parametrize("source, command", [
    ("a &amp;&amp; cd x", "cd"),
    ("a | tail", "tail"),
    ("T=$(uv run x)", "uv"),
])
def test_a_command_is_found_after_each_thing_that_starts_one(source, command):
    """Whitespace must not clear the expectation, or `&& cd` would miss `cd`."""
    marked = highlight(f'<pre data-lang="sh">{source}</pre>')

    assert f'<span class="k">{command}</span>' in marked


def test_a_flag_and_a_variable_are_told_apart():
    marked = highlight('<pre data-lang="sh">x --ttl 60 $TOKEN</pre>')

    assert '<span class="f">--ttl</span>' in marked
    assert '<span class="v">$TOKEN</span>' in marked


def test_a_json_key_is_told_apart_from_a_string_value():
    marked = highlight('<pre data-lang="json">{ "id": "1" }</pre>')

    assert '<span class="k">"id"</span>' in marked
    assert '<span class="s">"1"</span>' in marked


@pytest.mark.parametrize("template", sorted(web.PAGES.values()))
def test_no_page_ships_an_unrendered_language_attribute(template):
    assert "data-lang" not in web.page(template)


def test_the_pages_that_carry_code_come_out_coloured():
    assert '<span class="c">' in web.page(web.PAGES["/start"])
    assert '<span class="k">npx</span>' in web.page(web.PAGES["/operate"])
