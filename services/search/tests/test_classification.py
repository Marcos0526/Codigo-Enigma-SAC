"""Tests for query classification."""

import pytest

from services.search.src.classification.query_classifier import (
    QueryClassifier,
    CombustionSubtopic,
    ClassificationResult,
)


class TestQueryClassifier:
    """Tests for combustion query classification."""

    @pytest.fixture
    def classifier(self):
        return QueryClassifier()

    def test_combustion_temperature_query(self, classifier):
        """Test classification of temperature queries."""
        queries = [
            "combustion temperature measurements in microgravity",
            "flame temperature profile pyrometry",
            "thermal measurement combustion",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.COMBUSTION_TEMPERATURE
            assert result.confidence > 0.1
            assert result.is_combustion_related is True

    def test_flame_microgravity_query(self, classifier):
        """Test classification of microgravity flame queries."""
        queries = [
            "flame behavior in microgravity environment",
            "ISS combustion experiment low gravity",
            "orbital flame experiment space station",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.FLAME_MICROGRAVITY
            assert result.confidence > 0.1

    def test_flame_propagation_query(self, classifier):
        """Test classification of flame propagation queries."""
        queries = [
            "flame propagation speed solid materials",
            "burning rate flame spread PMMA",
            "flame velocity propagation",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.FLAME_PROPAGATION

    def test_extinction_query(self, classifier):
        """Test classification of extinction queries."""
        queries = [
            "extinction limits oxygen concentration suppressant",
            "flammability limit LOI quenching",
            "extinction boundary blowoff",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.EXTINCTION

    def test_soot_query(self, classifier):
        """Test classification of soot queries."""
        queries = [
            "soot formation volume fraction diffusion flames",
            "particulate carbon black carbon radiation",
            "soot concentration measurement",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.SOOT

    def test_aerosols_smoke_query(self, classifier):
        """Test classification of aerosol/smoke queries."""
        queries = [
            "smoke aerosol particle size distribution microgravity",
            "particle counter condensation nuclei",
            "aerosol measurement particle distribution",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.AEROSOLS_SMOKE

    def test_fire_safety_query(self, classifier):
        """Test classification of fire safety queries."""
        queries = [
            "spacecraft fire safety material flammability",
            "SAFFIRE experiment fire suppression",
            "BASS fire test habitat safety",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.FIRE_SAFETY

    def test_cool_flames_query(self, classifier):
        """Test classification of cool flames queries."""
        queries = [
            "cool flames low temperature chemistry extinction",
            "low temperature oxidation NTC cool flame",
            "cool flame limit negative temperature coefficient",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.COOL_FLAMES

    def test_solid_fuels_query(self, classifier):
        """Test classification of solid fuel queries."""
        queries = [
            "solid fuel combustion PMMA cellulose fabric",
            "material flammability pyrolysis solid",
            "condensed phase combustion solid",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.SOLID_FUELS

    def test_gaseous_fuels_query(self, classifier):
        """Test classification of gaseous fuel queries."""
        queries = [
            "gaseous fuel diffusion flame methane hydrogen",
            "premixed flame propagation ethylene",
            "nonpremixed combustion gas fuel",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.GASEOUS_FUELS

    def test_liquid_fuels_query(self, classifier):
        """Test classification of liquid fuel queries."""
        queries = [
            "liquid droplet combustion heptane spray",
            "droplet burning vaporization atomization",
            "liquid fuel spray combustion",
        ]

        for query in queries:
            result = classifier.classify(query)
            assert result.subtopic == CombustionSubtopic.LIQUID_FUELS

    def test_non_combustion_query(self, classifier):
        """Test classification of non-combustion queries."""
        queries = [
            "weather forecast tomorrow",
            "how to bake a cake",
            "stock market analysis",
        ]

        for query in queries:
            result = classifier.classify(query)
            # Should default to general combustion with low confidence
            assert result.subtopic == CombustionSubtopic.GENERAL_COMBUSTION
            assert result.confidence < 0.2

    def test_suggested_filters_temperature(self, classifier):
        """Test suggested filters for temperature queries."""
        result = classifier.classify("combustion temperature measurements")
        filters = result.suggested_filters

        assert "tags" in filters
        assert "formats" in filters
        assert "psi_ids" in filters
        assert "PSI-20" in filters.get("psi_ids", []) or "PSI-21" in filters.get("psi_ids", [])

    def test_suggested_filters_fire_safety(self, classifier):
        """Test suggested filters for fire safety queries."""
        result = classifier.classify("spacecraft fire safety")
        filters = result.suggested_filters

        assert "tags" in filters
        psi_ids = filters.get("psi_ids", [])
        assert any(psi in psi_ids for psi in ["PSI-98", "PSI-99", "PSI-100", "PSI-26"])

    def test_evaluation_queries(self, classifier):
        """Test evaluation queries are well-formed."""
        queries = classifier.get_evaluation_queries()

        assert len(queries) >= 10
        for q in queries:
            assert "query" in q
            assert "subtopic" in q
            assert q["subtopic"] in [s.value for s in CombustionSubtopic]

    def test_score_normalization(self, classifier):
        """Test that scores are normalized."""
        result = classifier.classify("combustion temperature")
        total = sum(result.all_scores.values())
        assert abs(total - 1.0) < 0.01

    def test_classification_result_dataclass(self):
        """Test ClassificationResult dataclass."""
        result = ClassificationResult(
            subtopic=CombustionSubtopic.COMBUSTION_TEMPERATURE,
            confidence=0.9,
            all_scores={CombustionSubtopic.COMBUSTION_TEMPERATURE: 0.9},
            suggested_filters={},
            is_combustion_related=True,
        )

        assert result.subtopic == CombustionSubtopic.COMBUSTION_TEMPERATURE
        assert result.confidence == 0.9
        assert result.is_combustion_related is True