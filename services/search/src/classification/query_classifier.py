"""Query classification for combustion science domain."""

import structlog
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from services.search.src.config import settings

logger = structlog.get_logger()


class CombustionSubtopic(str, Enum):
    """Combustion science subtopics for classification."""

    COMBUSTION_TEMPERATURE = "combustion_temperature"
    FLAME_MICROGRAVITY = "flame_microgravity"
    FLAME_PROPAGATION = "flame_propagation"
    EXTINCTION = "extinction"
    SOOT = "soot"
    AEROSOLS_SMOKE = "aerosols_smoke"
    FIRE_SAFETY = "fire_safety"
    COOL_FLAMES = "cool_flames"
    SOLID_FUELS = "solid_fuels"
    GASEOUS_FUELS = "gaseous_fuels"
    LIQUID_FUELS = "liquid_fuels"
    GENERAL_COMBUSTION = "general_combustion"


@dataclass
class ClassificationResult:
    """Result of query classification."""
    subtopic: CombustionSubtopic
    confidence: float
    all_scores: Dict[CombustionSubtopic, float]
    suggested_filters: Dict[str, List[str]]
    is_combustion_related: bool


class QueryClassifier:
    """Classifies queries into combustion science subtopics."""

    # Keyword patterns for each subtopic
    SUBTOPIC_KEYWORDS = {
        CombustionSubtopic.COMBUSTION_TEMPERATURE: [
            "temperature", "thermal", "heat", "pyrometry", "thermocouple",
            "flame temperature", "adiabatic", "heat release", "calorimetry",
            "temperature measurement", "thermal profile", "temperature field",
        ],
        CombustionSubtopic.FLAME_MICROGRAVITY: [
            "microgravity", "low gravity", "reduced gravity", "ISS", "space station",
            "orbital", "free fall", "drop tower", "parabolic flight",
            "space combustion", "orbital experiment",
        ],
        CombustionSubtopic.FLAME_PROPAGATION: [
            "propagation", "spread", "flame spread", "burning rate", "flame speed",
            "laminar flame", "turbulent flame", "deflagration", "detonation",
            "flame front", "reaction zone", "propagation velocity",
        ],
        CombustionSubtopic.EXTINCTION: [
            "extinction", "extinguish", "quenching", "blowoff", "blowout",
            "limiting oxygen", "LOI", "suppressant", "inerting",
            "extinction limit", "flammability limit", "extinction boundary",
        ],
        CombustionSubtopic.SOOT: [
            "soot", "particulate", "carbon", "black carbon", "smoke particle",
            "soot volume", "soot concentration", "soot formation", "soot oxidation",
            "radiative heat", "radiation", "emissivity", "absorption",
        ],
        CombustionSubtopic.AEROSOLS_SMOKE: [
            "aerosol", "smoke", "particle size", "particle distribution",
            "droplet", "condensation", "nucleation", "coagulation",
            "aerosol measurement", "particle counter", "optical particle",
        ],
        CombustionSubtopic.FIRE_SAFETY: [
            "fire safety", "fire suppression", "fire detection", "fire prevention",
            "spacecraft fire", "habitat fire", "material flammability",
            "fire experiment", "SAFFIRE", "BASS", "fire test",
        ],
        CombustionSubtopic.COOL_FLAMES: [
            "cool flame", "low temperature", "low-temperature", "cool flame",
            "negative temperature coefficient", "NTC", "two-stage ignition",
            "cool flame extinction", "cool flame limit", "low temperature chemistry",
        ],
        CombustionSubtopic.SOLID_FUELS: [
            "solid fuel", "solid material", "PMMA", "cellulose", "polymer",
            "fabric", "thermoplastic", "thermoset", "condensed phase",
            "pyrolysis", "solid combustion", "material flammability",
        ],
        CombustionSubtopic.GASEOUS_FUELS: [
            "gaseous fuel", "gas fuel", "methane", "hydrogen", "propane",
            "ethylene", "syngas", "natural gas", "premixed", "nonpremixed",
            "diffusion flame", "premixed flame", "gas combustion",
        ],
        CombustionSubtopic.LIQUID_FUELS: [
            "liquid fuel", "droplet", "spray", "atomization", "vaporization",
            "heptane", "decane", "kerosene", "JP-8", "biodiesel",
            "liquid combustion", "spray combustion", "droplet burning",
        ],
    }

    # PSI investigation tags for filtering
    SUBTOPIC_PSI_TAGS = {
        CombustionSubtopic.COMBUSTION_TEMPERATURE: ["temperature", "thermal", "pyrometry"],
        CombustionSubtopic.FLAME_MICROGRAVITY: ["microgravity", "iss", "orbital"],
        CombustionSubtopic.FLAME_PROPAGATION: ["flame-spread", "propagation", "burning-rate"],
        CombustionSubtopic.EXTINCTION: ["extinction", "flammability", "suppressant"],
        CombustionSubtopic.SOOT: ["soot", "particulate", "radiation"],
        CombustionSubtopic.AEROSOLS_SMOKE: ["smoke", "aerosol", "particle-size"],
        CombustionSubtopic.FIRE_SAFETY: ["fire-safety", "saffire", "bass", "material-flammability"],
        CombustionSubtopic.COOL_FLAMES: ["cool-flames", "low-temperature", "low-temperature-chemistry"],
        CombustionSubtopic.SOLID_FUELS: ["solid-fuels", "material-flammability", "pyrolysis"],
        CombustionSubtopic.GASEOUS_FUELS: ["gaseous-fuels", "diffusion-flames", "premixed"],
        CombustionSubtopic.LIQUID_FUELS: ["droplets", "liquid-fuels", "spray"],
    }

    def __init__(self):
        self._keyword_weights = self._build_keyword_weights()

    def _build_keyword_weights(self) -> Dict[CombustionSubtopic, Dict[str, float]]:
        """Build weighted keyword dictionary for each subtopic."""
        weights = {}
        for subtopic, keywords in self.SUBTOPIC_KEYWORDS.items():
            kw_weights = {}
            for i, kw in enumerate(keywords):
                # Higher weight for earlier/more specific keywords
                kw_weights[kw.lower()] = 1.0 - (i * 0.05)
            weights[subtopic] = kw_weights
        return weights

    def classify(self, query: str) -> ClassificationResult:
        """Classify a query into combustion subtopics."""
        query_lower = query.lower()
        words = query_lower.split()

        scores = {}
        for subtopic in CombustionSubtopic:
            score = 0.0
            kw_weights = self._keyword_weights.get(subtopic, {})

            # Track exact phrase matches separately
            phrase_matches = 0
            word_matches = 0

            for kw, weight in kw_weights.items():
                if kw in query_lower:
                    # Exact phrase match gets higher score
                    score += weight * 3.0
                    phrase_matches += 1
                else:
                    # Check individual words - more strict matching
                    for word in words:
                        # Only match if word is a significant part of keyword
                        if len(word) > 3 and (word == kw or kw.startswith(word) or word.startswith(kw)):
                            score += weight * 0.5
                            word_matches += 1

            # Boost score based on phrase matches
            if phrase_matches > 0:
                score *= (1 + phrase_matches * 0.5)

            # Normalize by square root of keyword count (less aggressive than linear)
            if kw_weights:
                score = score / (len(kw_weights) ** 0.5)

            scores[subtopic] = score

        # Find best match
        if scores:
            best_subtopic = max(scores, key=scores.get)
            best_score = scores[best_subtopic]
        else:
            best_subtopic = CombustionSubtopic.GENERAL_COMBUSTION
            best_score = 0.0

        # Check if combustion-related at all
        combustion_keywords = [
            "combustion", "flame", "fire", "burn", "ignition", "oxidation",
            "fuel", "reactant", "oxidizer", "chemistry", "kinetics",
        ]
        is_combustion = any(kw in query_lower for kw in combustion_keywords) or best_score > 0.05

        # For non-combustion queries, force GENERAL_COMBUSTION
        if not is_combustion:
            best_subtopic = CombustionSubtopic.GENERAL_COMBUSTION
            best_score = 0.0

        # Normalize scores to sum to 1
        total = sum(scores.values())
        if total > 0:
            normalized_scores = {k: v / total for k, v in scores.items()}
        else:
            normalized_scores = {k: 1.0 / len(scores) for k in scores}

        # Generate suggested filters
        suggested_filters = self._generate_filters(best_subtopic, query_lower)

        return ClassificationResult(
            subtopic=best_subtopic,
            confidence=min(best_score, 1.0),
            all_scores=normalized_scores,
            suggested_filters=suggested_filters,
            is_combustion_related=is_combustion,
        )

    def _generate_filters(self, subtopic: CombustionSubtopic, query: str) -> Dict[str, List[str]]:
        """Generate suggested search filters based on classification."""
        filters = {}

        # PSI investigation tags
        tags = self.SUBTOPIC_PSI_TAGS.get(subtopic, [])
        if tags:
            filters["tags"] = tags

        # Data format preferences based on subtopic
        format_map = {
            CombustionSubtopic.SOOT: ["csv", "parquet"],
            CombustionSubtopic.AEROSOLS_SMOKE: ["csv", "parquet"],
            CombustionSubtopic.COMBUSTION_TEMPERATURE: ["csv", "parquet"],
            CombustionSubtopic.FLAME_PROPAGATION: ["csv", "parquet"],
            CombustionSubtopic.EXTINCTION: ["csv", "parquet"],
        }
        if subtopic in format_map:
            filters["formats"] = format_map[subtopic]

        # Specific PSI IDs for well-known subtopics
        psi_map = {
            CombustionSubtopic.COMBUSTION_TEMPERATURE: ["PSI-20", "PSI-21", "PSI-69", "PSI-107", "PSI-159"],
            CombustionSubtopic.COOL_FLAMES: ["PSI-39", "PSI-159", "PSI-142", "PSI-117"],
            CombustionSubtopic.FIRE_SAFETY: ["PSI-98", "PSI-99", "PSI-100", "PSI-26", "PSI-25", "PSI-47"],
            CombustionSubtopic.SOOT: ["PSI-21", "PSI-10", "PSI-22", "PSI-60", "PSI-107"],
            CombustionSubtopic.FLAME_MICROGRAVITY: ["PSI-20", "PSI-21", "PSI-22", "PSI-23", "PSI-159"],
            CombustionSubtopic.FLAME_PROPAGATION: ["PSI-25", "PSI-62", "PSI-98", "PSI-99", "PSI-100"],
            CombustionSubtopic.GASEOUS_FUELS: ["PSI-20", "PSI-21", "PSI-10", "PSI-22", "PSI-23"],
            CombustionSubtopic.LIQUID_FUELS: ["PSI-39", "PSI-69", "PSI-107"],
            CombustionSubtopic.SOLID_FUELS: ["PSI-26", "PSI-25", "PSI-62"],
        }
        if subtopic in psi_map:
            filters["psi_ids"] = psi_map[subtopic]

        return filters

    def get_evaluation_queries(self) -> List[Dict[str, str]]:
        """Get evaluation queries for each subtopic."""
        return [
            {"query": "combustion temperature measurements in microgravity", "subtopic": "combustion_temperature"},
            {"query": "flame behavior in microgravity environment", "subtopic": "flame_microgravity"},
            {"query": "flame propagation speed solid materials", "subtopic": "flame_propagation"},
            {"query": "extinction limits oxygen concentration suppressant", "subtopic": "extinction"},
            {"query": "soot formation volume fraction diffusion flames", "subtopic": "soot"},
            {"query": "smoke aerosol particle size distribution microgravity", "subtopic": "aerosols_smoke"},
            {"query": "spacecraft fire safety material flammability", "subtopic": "fire_safety"},
            {"query": "cool flames low temperature chemistry extinction", "subtopic": "cool_flames"},
            {"query": "solid fuel combustion PMMA cellulose fabric", "subtopic": "solid_fuels"},
            {"query": "gaseous fuel diffusion flame methane hydrogen", "subtopic": "gaseous_fuels"},
            {"query": "liquid droplet combustion heptane spray", "subtopic": "liquid_fuels"},
        ]


class MLQueryClassifier(QueryClassifier):
    """ML-based query classifier using transformers (optional)."""

    def __init__(self, model_name: str = None):
        super().__init__()
        self.model_name = model_name or settings.CLASSIFICATION_MODEL
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        """Lazy load the classification model."""
        if self._model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch

            logger.info("loading_classification_model", model=self.model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._model.eval()

    def classify(self, query: str) -> ClassificationResult:
        """Classify using ML model with keyword fallback."""
        # Try ML classification first
        try:
            self._load_model()
            return self._ml_classify(query)
        except Exception as e:
            logger.warning("ml_classification_failed", error=str(e))
            # Fall back to keyword-based
            return super().classify(query)

    def _ml_classify(self, query: str) -> ClassificationResult:
        """Classify using the ML model."""
        import torch

        inputs = self._tokenizer(
            query,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)

        # Map model outputs to subtopics
        # This assumes the model was trained on the same label set
        labels = settings.CLASSIFICATION_LABELS
        scores = {CombustionSubtopic(labels[i]): float(probs[0][i]) for i in range(len(labels))}

        best_subtopic = max(scores, key=scores.get)
        best_score = scores[best_subtopic]

        return ClassificationResult(
            subtopic=best_subtopic,
            confidence=best_score,
            all_scores=scores,
            suggested_filters=self._generate_filters(best_subtopic, query.lower()),
            is_combustion_related=best_score > 0.1,
        )