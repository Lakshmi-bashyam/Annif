"""Backend that returns most similar subjects based on similarity in sparse
TF-IDF normalized bag-of-words vector space"""

import collections
import os.path
import gensim.models
import gensim.similarities
import annif.corpus
import annif.util
from annif.hit import AnalysisHit
from . import backend


class VectorCorpus:
    """A class that wraps a subject corpus so it can be iterated as lists of
    vectors, by using a dictionary to map words to integers."""

    def __init__(self, corpus, dictionary, analyzer):
        self.corpus = corpus
        self.dictionary = dictionary
        self.analyzer = analyzer

    def __iter__(self):
        """Iterate through the subject directory, yielding vectors that are
        derived from subjects using the given analyzer and dictionary."""

        for subject in self.corpus:
            yield self.dictionary.doc2bow(
                self.analyzer.tokenize_words(subject.text))


class TFIDFBackend(backend.AnnifBackend):
    name = "tfidf"

    # top K subjects per chunk to consider
    MAX_CHUNK_SUBJECTS = 100

    # defaults for uninitialized instances
    _tfidf = None
    _index = None

    def _initialize_tfidf(self):
        if self._tfidf is None:
            path = os.path.join(self._get_datadir(), 'tfidf')
            self.debug('loading TF-IDF model from {}'.format(path))
            self._tfidf = gensim.models.TfidfModel.load(path)

    def _initialize_index(self):
        if self._index is None:
            path = os.path.join(self._get_datadir(), 'index')
            self.debug('loading similarity index from {}'.format(path))
            self._index = gensim.similarities.SparseMatrixSimilarity.load(path)

    def initialize(self):
        self._initialize_tfidf()
        self._initialize_index()

    def load_subjects(self, subjects, project):
        veccorpus = VectorCorpus(subjects,
                                 project.dictionary,
                                 project.analyzer)
        self.info('creating TF-IDF model')
        self._tfidf = gensim.models.TfidfModel(veccorpus)
        annif.util.atomic_save(self._tfidf, self._get_datadir(), 'tfidf')
        self.info('creating similarity index')
        self._index = gensim.similarities.SparseMatrixSimilarity(
            self._tfidf[veccorpus], num_features=len(project.dictionary))
        annif.util.atomic_save(self._index, self._get_datadir(), 'index')

    def _analyze_chunks(self, chunks):
        results = []
        for docsim in self._index[chunks]:
            sims = sorted(
                enumerate(docsim),
                key=lambda item: item[1],
                reverse=True)
            results.append(sims[:self.MAX_CHUNK_SUBJECTS])
        return results

    def _merge_chunk_results(self, chunk_results, project):
        subject_scores = collections.defaultdict(float)
        for result in chunk_results:
            for subject_id, score in result:
                subject_scores[subject_id] += score
        best_subjects = sorted([(score,
                                 subject_id) for subject_id,
                                score in subject_scores.items()],
                               reverse=True)
        limit = int(self.params['limit'])
        results = []
        for score, subject_id in best_subjects[:limit]:
            if score <= 0.0:
                continue
            subject = project.subjects[subject_id]
            results.append(
                AnalysisHit(
                    subject[0],
                    subject[1],
                    score /
                    len(chunk_results)))
        return results

    def _analyze(self, text, project, params):
        self.initialize()
        self.debug('Analyzing text "{}..." (len={})'.format(
            text[:20], len(text)))
        sentences = project.analyzer.tokenize_sentences(text)
        self.debug('Found {} sentences'.format(len(sentences)))
        chunksize = int(params['chunksize'])
        chunks = []  # chunks represented as TF-IDF normalized vectors
        for i in range(0, len(sentences), chunksize):
            chunktext = ' '.join(sentences[i:i + chunksize])
            chunkbow = project.dictionary.doc2bow(
                project.analyzer.tokenize_words(chunktext))
            chunks.append(self._tfidf[chunkbow])
        self.debug('Split sentences into {} chunks'.format(len(chunks)))
        chunk_results = self._analyze_chunks(chunks)
        return self._merge_chunk_results(chunk_results, project)
