"""Simple analyzer for Annif. Only folds words to lower case."""

import spacy
from . import analyzer
import annif.util

_KEY_LOWERCASE = 'lowercase'


class SpacyAnalyzer(analyzer.Analyzer):
    name = "spacy"

    def __init__(self, param, **kwargs):
        self.param = param
        self.nlp = spacy.load(param, exclude=['ner', 'parser'])
        if _KEY_LOWERCASE in kwargs:
            self.lowercase = annif.util.boolean(kwargs[_KEY_LOWERCASE])
        else:
            self.lowercase = False
        super().__init__(**kwargs)

    def tokenize_words(self, text):
        lemmas = [lemma for lemma in (token.lemma_ for token in self.nlp(text))
                  if self.is_valid_token(lemma)]
        if self.lowercase:
            return [lemma.lower() for lemma in lemmas]
        else:
            return lemmas

    def normalize_word(self, word):
        doc = self.nlp(word)
        lemma = doc[:].lemma_
        if self.lowercase:
            return lemma.lower()
        else:
            return lemma
