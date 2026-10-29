"""Keeping whitespace must retain source layout rather than adding spacing."""

import pytest

from lua_minifier import Minifier, MinifyOptions


@pytest.mark.parametrize('source', [
    'local  x = 1\n\n\tprint( x )\n\n',
    '-- heading\r\nlocal x = 1\r\n-- tail\r\n',
    'local --[[inline]] x = 1\nprint(x)\n',
    'local x = 1\rprint(x)\r',
    'local x = 1\n\rprint(x)\n\r',
    '\t \n\n',
])
def test_disabled_transforms_preserve_existing_whitespace(source):
    options = MinifyOptions(remove_whitespace=False, remove_comments=False,
                            minify_strings=False, minify_numbers=False)
    assert Minifier(options).minify(source).output == source


def test_comment_removal_does_not_remove_surrounding_layout():
    source = '-- heading\nlocal  x = 1 -- inline\n\nprint(x)\n'
    options = MinifyOptions(remove_whitespace=False)
    assert Minifier(options).minify(source).output == '\nlocal  x = 1 \n\nprint(x)\n'


def test_kept_short_comment_still_terminates_when_whitespace_is_removed():
    options = MinifyOptions(remove_comments=False)
    assert Minifier(options).minify('-- heading\nprint(1)').output == '-- heading\nprint(1)\n'


def test_whitespace_removal_remains_enabled_by_default():
    assert Minifier().minify('local  x = 1\n\n\tprint( x )\n\n').output == 'local x=1 print(x)\n'


def test_preservation_still_adds_missing_final_newline():
    options = MinifyOptions(remove_whitespace=False)
    assert Minifier(options).minify('print( 1 )').output == 'print( 1 )\n'


@pytest.mark.parametrize('ending', ['\n', '\r', '\r\n', '\n\r'])
def test_keep_newlines_retains_blank_lines_without_preserving_spaces(ending):
    source = 'print ( 1 )' + ending * 2 + 'print ( 2 )' + ending * 2
    options = MinifyOptions(keep_newlines=True)
    assert Minifier(options).minify(source).output == 'print(1)' + ending * 2 + 'print(2)' + ending * 2


def test_keep_newlines_applies_to_whitespace_only_input():
    options = MinifyOptions(keep_newlines=True)
    assert Minifier(options).minify(' \n\t\n\n').output == '\n\n\n'
