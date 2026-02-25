"""
Pattern Detection for RSCT Pre-screening

Detects:
- Injection attempts
- Spam/promotional content
- Gibberish/nonsense
- Harmful patterns

These patterns affect the N (noise) and R (relevance) scores.
"""

from __future__ import annotations

import re
import string
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class PatternMatch:
    """Result of pattern matching."""
    category: str
    score: float  # 0-1, higher = more problematic
    details: str


class PatternDetector:
    """
    Detects problematic patterns in prompts.

    Returns scores that modify RSN computation:
    - High noise_boost → increases N
    - Low relevance_factor → decreases R
    """

    # Injection patterns
    INJECTION_PATTERNS = [
        (r'ignore\s+(all\s+)?previous\s+instructions', 0.9, 'injection'),
        (r'disregard\s+(all\s+)?(prior|previous|above)', 0.9, 'injection'),
        (r'forget\s+(everything|all|what)', 0.8, 'injection'),
        (r'you\s+are\s+now\s+(a|in)', 0.7, 'roleplay_injection'),
        (r'pretend\s+(you\'?re?|to\s+be)', 0.6, 'roleplay_injection'),
        (r'SYSTEM:', 0.8, 'fake_system'),
        (r'\[INST\]|\[/INST\]', 0.8, 'format_injection'),
        (r'<\|im_start\|>|<\|im_end\|>', 0.8, 'format_injection'),
        (r'```system|```instruction', 0.7, 'format_injection'),
        (r'override\s+(safety|restrictions|rules)', 0.95, 'jailbreak'),
        (r'jailbreak|DAN\s+mode|developer\s+mode', 0.95, 'jailbreak'),
    ]

    # Spam patterns
    SPAM_PATTERNS = [
        (r'BUY\s+NOW|CLICK\s+HERE|FREE\s+MONEY', 0.9, 'spam'),
        (r'ACT\s+NOW|LIMITED\s+TIME|URGENT', 0.7, 'urgency_spam'),
        (r'💎🙌|🚀{2,}|TO\s+THE\s+MOON', 0.8, 'crypto_spam'),
        (r'(WIN|EARN|GET)\s+\$?\d+', 0.7, 'money_spam'),
        (r'subscribe.*channel|like.*comment', 0.6, 'social_spam'),
    ]

    # XSS/Code injection
    CODE_INJECTION_PATTERNS = [
        (r'<script[^>]*>', 0.95, 'xss'),
        (r'javascript:', 0.9, 'xss'),
        (r'on(click|load|error|mouse)\s*=', 0.9, 'xss'),
        (r'</?(prompt|system|user|assistant)>', 0.8, 'tag_injection'),
        (r'\{\{.*\}\}', 0.6, 'template_injection'),
        (r'eval\s*\(|exec\s*\(', 0.9, 'code_injection'),
    ]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns."""
        self.compiled = []
        all_patterns = (
            self.INJECTION_PATTERNS +
            self.SPAM_PATTERNS +
            self.CODE_INJECTION_PATTERNS
        )
        for pattern, score, category in all_patterns:
            try:
                self.compiled.append((
                    re.compile(pattern, re.IGNORECASE),
                    score,
                    category,
                ))
            except re.error:
                pass

    def detect(self, text: str) -> List[PatternMatch]:
        """
        Detect all problematic patterns in text.

        Returns list of matches sorted by score (highest first).
        """
        matches = []

        for regex, score, category in self.compiled:
            if regex.search(text):
                matches.append(PatternMatch(
                    category=category,
                    score=score,
                    details=regex.pattern[:50],
                ))

        # Check for gibberish
        gibberish_score = self._detect_gibberish(text)
        if gibberish_score > 0.5:
            matches.append(PatternMatch(
                category='gibberish',
                score=gibberish_score,
                details=f'gibberish_score={gibberish_score:.2f}',
            ))

        # Check for repetition
        repetition_score = self._detect_repetition(text)
        if repetition_score > 0.5:
            matches.append(PatternMatch(
                category='repetition',
                score=repetition_score,
                details=f'repetition_score={repetition_score:.2f}',
            ))

        # Sort by score
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    def _detect_gibberish(self, text: str) -> float:
        """
        Detect gibberish/random text.

        Checks:
        - Vowel ratio (English ~38%)
        - Common bigrams
        - Word length distribution
        """
        if not text or len(text) < 3:
            return 0.6  # Too short is suspicious

        # Clean text
        clean = text.lower()
        letters = [c for c in clean if c.isalpha()]

        if not letters:
            # No letters = likely gibberish or punctuation only
            return 0.8

        # Vowel ratio check
        vowels = set('aeiou')
        vowel_count = sum(1 for c in letters if c in vowels)
        vowel_ratio = vowel_count / len(letters)

        # English typically 35-42% vowels
        if vowel_ratio < 0.15 or vowel_ratio > 0.6:
            return 0.7

        # Check for common English bigrams
        common_bigrams = {'th', 'he', 'in', 'er', 'an', 'on', 'en', 'at', 'es', 'ed'}
        text_bigrams = set(clean[i:i+2] for i in range(len(clean)-1))
        bigram_overlap = len(text_bigrams & common_bigrams)

        if len(text) > 20 and bigram_overlap < 2:
            return 0.6

        # Check for impossible consonant clusters
        impossible = re.findall(r'[bcdfghjklmnpqrstvwxz]{5,}', clean)
        if impossible:
            return 0.8

        return 0.0

    def _detect_repetition(self, text: str) -> float:
        """Detect excessive repetition."""
        if len(text) < 10:
            return 0.0

        words = text.lower().split()
        if len(words) < 3:
            return 0.0

        # Check word repetition
        unique_words = set(words)
        repetition_ratio = 1 - (len(unique_words) / len(words))

        if repetition_ratio > 0.7:
            return 0.8
        elif repetition_ratio > 0.5:
            return 0.5

        # Check for repeated phrases
        for phrase_len in [2, 3, 4]:
            if len(words) >= phrase_len * 3:
                phrases = [' '.join(words[i:i+phrase_len]) for i in range(len(words) - phrase_len + 1)]
                phrase_counts = {}
                for p in phrases:
                    phrase_counts[p] = phrase_counts.get(p, 0) + 1
                max_repeat = max(phrase_counts.values())
                if max_repeat >= 3:
                    return 0.7

        return 0.0

    def get_noise_boost(self, matches: List[PatternMatch]) -> float:
        """
        Calculate noise boost from pattern matches.

        Returns value to ADD to N score.
        """
        if not matches:
            return 0.0

        # Use highest match score, with diminishing returns for multiple
        max_score = matches[0].score
        additional = sum(m.score * 0.1 for m in matches[1:4])

        return min(0.5, max_score * 0.4 + additional)

    def get_relevance_factor(self, matches: List[PatternMatch]) -> float:
        """
        Calculate relevance reduction factor.

        Returns multiplier for R score (1.0 = no change, 0.5 = halve R).
        """
        if not matches:
            return 1.0

        # Reduce based on severity
        max_score = matches[0].score

        if max_score > 0.8:
            return 0.3  # Severe reduction
        elif max_score > 0.6:
            return 0.5
        elif max_score > 0.4:
            return 0.7

        return 0.9


# Global instance
_detector = None

def get_detector() -> PatternDetector:
    """Get global pattern detector instance."""
    global _detector
    if _detector is None:
        _detector = PatternDetector()
    return _detector
