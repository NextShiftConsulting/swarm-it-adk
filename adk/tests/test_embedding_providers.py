"""
Tests for embedding providers and kappa viability checking.

These tests ensure parameter validation, error handling, and correct
integration between providers.
"""

import pytest
import numpy as np

from swarm_it.providers.embedding import (
    TidyLLMSentenceProvider,
    SentenceTransformerProvider,
    KappaViabilityChecker,
    check_kappa,
    compute_kappa,
    compute_stable_rank,
    get_provider,
)


class TestTidyLLMSentenceProviderValidation:
    """Test parameter validation for TidyLLMSentenceProvider."""

    def test_sif_without_glove_path_raises_valueerror(self):
        """SIF method without glove_path should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            TidyLLMSentenceProvider(method='sif')

        error_msg = str(exc_info.value)
        assert 'glove_path' in error_msg
        assert 'sif' in error_msg

    def test_sif_with_explicit_none_glove_path_raises(self):
        """SIF method with explicit None glove_path should raise."""
        with pytest.raises(ValueError):
            TidyLLMSentenceProvider(method='sif', glove_path=None)

    def test_lsa_method_works_without_glove(self):
        """LSA method should work without glove_path."""
        provider = TidyLLMSentenceProvider(method='lsa')
        assert provider.dim == 384
        assert provider.model_name == 'tidyllm-lsa-384'

    def test_power_mean_method_works(self):
        """Power mean method should work without glove_path."""
        provider = TidyLLMSentenceProvider(method='power_mean')
        assert provider.dim == 384

    def test_tfidf_method_works(self):
        """TF-IDF method should work."""
        provider = TidyLLMSentenceProvider(method='tfidf')
        assert provider.dim == 384

    def test_custom_embedding_dim(self):
        """Custom embedding_dim should be respected."""
        provider = TidyLLMSentenceProvider(embedding_dim=64)
        assert provider.dim == 64


class TestTidyLLMSentenceProviderFunctionality:
    """Test embedding generation functionality."""

    def test_embed_returns_correct_shape(self):
        """Embedding should return correct numpy array shape."""
        provider = TidyLLMSentenceProvider(embedding_dim=384, method='lsa')
        texts = ['Hello world', 'Machine learning', 'Deep networks']
        embeddings = provider.embed(texts)

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 384)
        assert embeddings.dtype == np.float32

    def test_embed_single_text(self):
        """Single text should work correctly."""
        provider = TidyLLMSentenceProvider(method='lsa')
        embeddings = provider.embed(['Single sentence'])

        assert embeddings.shape == (1, 384)

    def test_model_name_format(self):
        """Model name should follow tidyllm-{method}-{dim} format."""
        provider = TidyLLMSentenceProvider(embedding_dim=64, method='lsa')
        assert provider.model_name == 'tidyllm-lsa-64'


class TestKappaViability:
    """Test kappa viability checking."""

    def test_check_kappa_returns_result(self):
        """check_kappa should return KappaResult."""
        embeddings = np.random.randn(10, 384).astype(np.float32)
        result = check_kappa(embeddings)

        assert hasattr(result, 'kappa')
        assert hasattr(result, 'stable_rank')
        assert hasattr(result, 'is_viable')
        assert hasattr(result, 'recommended_k')

    def test_high_dim_low_variance_is_viable(self):
        """High dimension with spread variance should be viable."""
        # Create embeddings with good spread
        embeddings = np.random.randn(100, 384).astype(np.float32)
        result = check_kappa(embeddings)

        # With random data, kappa should be reasonably high
        assert result.kappa > 1.0
        assert result.dim == 384

    def test_recommended_k_calculation(self):
        """Recommended k should follow formula k = min(ceil(65/kappa), 5)."""
        checker = KappaViabilityChecker(threshold=50.0)

        # kappa = 10 -> k = ceil(65/10) = 7, capped at 5
        assert checker.optimal_k(10) == 5

        # kappa = 30 -> k = ceil(65/30) = 3
        assert checker.optimal_k(30) == 3

        # kappa = 100 -> already viable, k = 1
        assert checker.optimal_k(100) == 1

    def test_check_kappa_accepts_list_input(self):
        """check_kappa should accept nested list input."""
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
        result = check_kappa(embeddings)

        assert result.dim == 3


class TestGetProviderFactory:
    """Test get_provider factory function."""

    def test_get_tidyllm_provider(self):
        """get_provider('tidyllm') should return TidyLLMSentenceProvider."""
        provider = get_provider('tidyllm', embedding_dim=64, method='lsa')

        assert isinstance(provider, TidyLLMSentenceProvider)
        assert provider.dim == 64

    def test_get_tidyllm_sentence_alias(self):
        """get_provider('tidyllm-sentence') should also work."""
        provider = get_provider('tidyllm-sentence', method='lsa')

        assert isinstance(provider, TidyLLMSentenceProvider)

    def test_unknown_provider_raises(self):
        """Unknown provider type should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_provider('unknown_provider')

        assert 'unknown_provider' in str(exc_info.value).lower()


class TestStableRankComputation:
    """Test stable rank computation edge cases."""

    def test_single_embedding_returns_one(self):
        """Single embedding should return stable_rank = 1.0."""
        embeddings = np.array([[1.0, 2.0, 3.0]])
        stable_rank = compute_stable_rank(embeddings)
        assert stable_rank == 1.0

    def test_identical_embeddings(self):
        """Identical embeddings should have low stable rank."""
        embeddings = np.array([
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0],
        ])
        stable_rank = compute_stable_rank(embeddings)
        # All identical -> variance is 0 -> stable rank approaches 1
        assert stable_rank >= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
