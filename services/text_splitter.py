import re
from typing import List

def split_script_into_chunks(text: str, max_words: int = 1600) -> List[str]:
    """
    Divide um roteiro em blocos com no máximo `max_words` palavras cada.
    Garante que os cortes sejam feitos estritamente em pontuações de fim de frase.
    """
    text = text.strip()
    if not text:
        return []

    words = text.split()
    if len(words) <= max_words:
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        sentence_words = sentence.split()
        sentence_word_count = len(sentence_words)

        if sentence_word_count > max_words:
            words_in_sentence = sentence_words
            for i in range(0, len(words_in_sentence), max_words):
                chunks.append(" ".join(words_in_sentence[i:i + max_words]))
            continue

        if current_word_count + sentence_word_count <= max_words:
            current_chunk.append(sentence)
            current_word_count += sentence_word_count
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_word_count = sentence_word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
