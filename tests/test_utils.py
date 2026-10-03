from app.utils import split_into_parts, count_words

def test_count_words():
    assert count_words('Hello world!') == 2

def test_split_keeps_sentence_boundaries():
    text = 'One two. Three four. Five six.'
    parts = split_into_parts(text, 4)
    assert parts == ['One two. Three four.', 'Five six.']

def test_split_handles_long_sentence_without_infinite_loop():
    text = ' '.join(['word'] * 10) + '.'
    parts = split_into_parts(text, 4)
    assert all(count_words(p) <= 4 for p in parts)
