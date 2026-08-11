"""Lazy-loading spaCy NLP engine for Presidio.

The stock ``SpacyNlpEngine`` loads *every* configured language model eagerly at
startup — with large models that means several gigabytes of downloads and RAM
before a single request can be served. This engine loads one small spaCy model
per language on first use (with a bounded LRU cache), so cold start is near
instant and memory only grows for languages actually requested.

Models are the ``_sm`` (small) variants — roughly 10-15 MB each versus ~500 MB
for the ``_lg`` models — which keeps the deployment footprint small while still
providing the NER (PERSON, LOCATION, DATE_TIME, ...) that Presidio needs for
contextual detection. Regex-backed PII (email, phone, Aadhaar, PAN, cards, ...)
does not depend on the NLP model at all.
"""

import logging
from collections import OrderedDict

import spacy

from presidio_analyzer.nlp_engine import SpacyNlpEngine

logger = logging.getLogger("presidio-analyzer")


class LazySpacyNlpEngine(SpacyNlpEngine):
    """SpacyNlpEngine variant that loads models lazily per language."""

    # Upper bound on how many language models are kept in memory at once.
    # Least-recently-used models are evicted beyond this limit.
    max_cached_models = 5

    def load(self) -> None:
        """Initialize the model cache. No model is loaded until first use."""
        self.nlp = OrderedDict()

    def is_loaded(self) -> bool:
        """Return True (the engine itself is always "ready"; models load on demand)."""
        return self.nlp is not None

    def process_text(self, text: str, language: str):
        """Run the spaCy pipeline for the given language, loading it lazily."""
        nlp = self._get_model(language)
        doc = nlp(text)
        return self._doc_to_nlp_artifact(doc, language)

    def process_batch(self, texts, language, as_tuples=False):
        """Process a batch of texts for the given language."""
        nlp = self._get_model(language)
        texts = (str(text) for text in texts)
        docs = nlp.pipe(texts, as_tuples=as_tuples)
        for doc in docs:
            yield doc.text, self._doc_to_nlp_artifact(doc, language)

    def is_stopword(self, word: str, language: str) -> bool:
        """Return True if the word is a stop word in the given language."""
        return self._get_model(language).vocab[word].is_stop

    def is_punct(self, word: str, language: str) -> bool:
        """Return True if the word is punctuation in the given language."""
        return self._get_model(language).vocab[word].is_punct

    def get_nlp(self, language: str):
        """Return the spaCy model loaded for a language (loading it lazily)."""
        return self._get_model(language)

    def _model_name_for(self, language: str) -> str:
        for entry in self.models:
            if entry["lang_code"] == language:
                return entry["model_name"]
        raise ValueError(f"No model configured for language '{language}'")

    def _get_model(self, language: str):
        if not self.nlp:
            self.load()

        if language in self.nlp:
            # Refresh LRU position
            self.nlp.move_to_end(language)
            return self.nlp[language]

        model_name = self._model_name_for(language)
        if not spacy.util.is_package(model_name):
            # Model not installed (e.g. local dev with a partial install).
            # Fall back to the English model so regex-backed PII detection
            # keeps working; log instead of silently degrading.
            fallback = self._model_name_for("en")
            logger.warning(
                "Model %s not installed for '%s'; falling back to %s",
                model_name,
                language,
                fallback,
            )
            model_name = fallback

        if not spacy.util.is_package(model_name):
            raise OSError(
                f"spaCy model '{model_name}' is not installed. "
                f"Install the model wheels from requirements.txt."
            )

        logger.info("Loading spaCy model '%s' (lazy, language=%s)", model_name, language)
        nlp = spacy.load(model_name)
        self.nlp[language] = nlp
        self.nlp.move_to_end(language)

        # Evict least-recently-used models beyond the cache bound
        while len(self.nlp) > self.max_cached_models:
            evicted = self.nlp.popitem(last=False)
            logger.info("Evicting cached model for language '%s'", evicted[0])

        return nlp
