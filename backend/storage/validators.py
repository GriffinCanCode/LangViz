"""Data validation rules and quality checks.

Composable validators following functional patterns.
"""

from typing import Protocol, Callable
from dataclasses import dataclass
import re
from backend.core.types import Entry, Language


class ValidationRule(Protocol):
    """Protocol for validation rules."""
    
    def __call__(self, value: object) -> tuple[bool, str]:
        """Validate value, return (is_valid, error_message)."""
        ...


@dataclass(frozen=True)
class RequiredField:
    """Validates that a field is present and non-empty."""
    
    field_name: str
    
    def __call__(self, entry: Entry) -> tuple[bool, str]:
        value = getattr(entry, self.field_name, None)
        
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, f"{self.field_name} is required"
        
        return True, ""


@dataclass(frozen=True)
class MinLength:
    """Validates minimum length of string field."""
    
    field_name: str
    min_length: int
    
    def __call__(self, entry: Entry) -> tuple[bool, str]:
        value = getattr(entry, self.field_name, "")
        
        if len(value) < self.min_length:
            return False, f"{self.field_name} must be at least {self.min_length} characters"
        
        return True, ""


@dataclass(frozen=True)
class MaxLength:
    """Validates maximum length of string field."""
    
    field_name: str
    max_length: int
    
    def __call__(self, entry: Entry) -> tuple[bool, str]:
        value = getattr(entry, self.field_name, "")
        
        if len(value) > self.max_length:
            return False, f"{self.field_name} must be at most {self.max_length} characters"
        
        return True, ""


@dataclass(frozen=True)
class RegexMatch:
    """Validates field matches regex pattern."""
    
    field_name: str
    pattern: str
    description: str
    
    def __call__(self, entry: Entry) -> tuple[bool, str]:
        value = getattr(entry, self.field_name, "")
        
        if not re.match(self.pattern, value):
            return False, f"{self.field_name} {self.description}"
        
        return True, ""


@dataclass(frozen=True)
class IPAValidator:
    """Validates IPA transcription format."""
    
    def __call__(self, entry: Entry) -> tuple[bool, str]:
        ipa = entry.ipa
        
        # Check for common errors
        if not ipa or not ipa.strip():
            return False, "IPA transcription is empty"
        
        # Check for invalid characters (basic check)
        if re.search(r'[0-9]', ipa) and not re.search(r'[ː̯̥̆̊]', ipa):
            return False, "IPA contains suspicious numeric characters"
        
        # Check for balanced brackets
        if ipa.count('[') != ipa.count(']'):
            return False, "IPA has unbalanced brackets"
        
        return True, ""


@dataclass(frozen=True)
class LanguageCodeValidator:
    """Validates ISO language codes."""
    
    # Common ISO 639 codes for Indo-European
    valid_codes = {
        'en', 'de', 'nl', 'sv', 'no', 'da', 'is', 'fo',  # Germanic
        'fr', 'es', 'it', 'pt', 'ro', 'ca', 'la',        # Romance
        'ru', 'pl', 'cs', 'sk', 'uk', 'bg', 'lt', 'lv',  # Slavic/Baltic
        'grc', 'el',                                      # Greek
        'sa', 'hi', 'ur', 'fa', 'ku', 'ps',              # Indo-Iranian
        'ga', 'cy', 'br', 'sga',                          # Celtic
        'sq',                                             # Albanian
        'hy',                                             # Armenian
        'pie', 'ine',                                     # Proto-languages
    }
    
    def __call__(self, entry: Entry) -> tuple[bool, str]:
        code = entry.language.lower()
        
        if code not in self.valid_codes:
            return False, f"Unknown or non-Indo-European language code: {code}"
        
        return True, ""


class EntryValidator:
    """Composite validator for Entry objects."""
    
    def __init__(self, rules: list[ValidationRule]):
        self._rules = rules
    
    def validate(self, entry: Entry) -> tuple[bool, list[str]]:
        """Validate entry against all rules.
        
        Returns (is_valid, error_messages).
        """
        errors = []
        
        for rule in self._rules:
            is_valid, error = rule(entry)
            if not is_valid:
                errors.append(error)
        
        return len(errors) == 0, errors
    
    def batch_validate(
        self,
        entries: list[Entry]
    ) -> dict[str, list[str]]:
        """Validate multiple entries, return map of ID to errors."""
        results = {}
        
        for entry in entries:
            is_valid, errors = self.validate(entry)
            if not is_valid:
                results[entry.id] = errors
        
        return results


class ValidatorFactory:
    """Factory for common validator configurations."""
    
    @staticmethod
    def standard_entry_validator() -> EntryValidator:
        """Standard validation rules for entries."""
        rules = [
            RequiredField('headword'),
            RequiredField('ipa'),
            RequiredField('language'),
            RequiredField('definition'),
            MinLength('headword', 1),
            MinLength('definition', 3),
            MaxLength('headword', 255),
            MaxLength('ipa', 255),
            IPAValidator(),
            LanguageCodeValidator(),
        ]
        return EntryValidator(rules)
    
    @staticmethod
    def strict_entry_validator() -> EntryValidator:
        """Strict validation requiring all fields."""
        rules = [
            RequiredField('headword'),
            RequiredField('ipa'),
            RequiredField('language'),
            RequiredField('definition'),
            RequiredField('etymology'),
            RequiredField('pos_tag'),
            MinLength('headword', 1),
            MinLength('definition', 10),
            MinLength('etymology', 5),
            MaxLength('headword', 255),
            MaxLength('ipa', 255),
            IPAValidator(),
            LanguageCodeValidator(),
        ]
        return EntryValidator(rules)
    
    @staticmethod
    def permissive_entry_validator() -> EntryValidator:
        """Permissive validation for low-quality sources."""
        rules = [
            RequiredField('headword'),
            RequiredField('language'),
            MinLength('headword', 1),
        ]
        return EntryValidator(rules)


def compute_quality_score(entry: Entry, validator: EntryValidator) -> float:
    """Compute quality score (0.0 - 1.0) based on validation.
    
    Returns 1.0 for perfect, decreasing based on missing/invalid fields.
    """
    is_valid, errors = validator.validate(entry)
    
    if is_valid:
        return 1.0
    
    # Penalize based on number of errors
    penalty = min(0.15 * len(errors), 0.9)
    return 1.0 - penalty

