"""Cleanup recommendation rules for Temp Cleaner."""

from enum import Enum
import os


class RecommendationStatus(Enum):
    CANDIDATE = "Candidate"
    REVIEW = "Review"
    DO_NOT_CLEAN = "Do not clean"
    UNKNOWN = "Unknown"


class CleanupRuleEngine:
    def evaluate(self, file_info, intel):
        file_info = file_info or {}
        intel = intel or {}
        errors = []

        path = file_info.get('path') or ''
        if not path:
            return {
                'status': RecommendationStatus.REVIEW.value,
                'reasons': ['Missing file path.'],
                'evidence': [],
                'errors': [],
            }

        # Require validated file record
        try:
            if not os.path.isabs(path):
                return {
                    'status': RecommendationStatus.REVIEW.value,
                    'reasons': ['Path validation failed.'],
                    'evidence': [],
                    'errors': [],
                }
            if not os.path.exists(path):
                return {
                    'status': RecommendationStatus.REVIEW.value,
                    'reasons': ['File does not exist or is inaccessible.'],
                    'evidence': [],
                    'errors': [],
                }
            if not os.path.isfile(path):
                return {
                    'status': RecommendationStatus.REVIEW.value,
                    'reasons': ['Item is not a regular file.'],
                    'evidence': [],
                    'errors': [],
                }
        except Exception:
            return {
                'status': RecommendationStatus.REVIEW.value,
                'reasons': ['Path validation failed.'],
                'evidence': [],
                'errors': [],
            }

        # Block if in use
        if intel.get('in_use') == 'In use':
            return {
                'status': RecommendationStatus.DO_NOT_CLEAN.value,
                'reasons': ['Windows reports a process using this file.'],
                'evidence': ['Restart Manager file-use detection'],
                'errors': [],
            }

        # Require review if usage unknown/not checked
        if intel.get('in_use') in ('Unknown', 'Unsupported', 'Not checked'):
            return {
                'status': RecommendationStatus.REVIEW.value,
                'reasons': ['File-use check not conclusive or not run.'],
                'evidence': ['File-use status: %s' % intel.get('in_use')],
                'errors': [],
            }

        # Check for generic extension only
        ext = path.lower().split('.')[-1] if '.' in path else ''
        purpose = intel.get('purpose', '')
        if purpose == 'Temporary file' and intel.get('app_method') == 'none' and ext in ('tmp', 'temp'):
            return {
                'status': RecommendationStatus.REVIEW.value,
                'reasons': ['Generic temporary extension with no strong evidence.'],
                'evidence': ['Extension-based classification'],
                'errors': [],
            }

        # Candidate for recognized patterns with evidence - requires validated file
        if intel.get('app_method') == 'directory' and intel.get('confidence') in ('Medium', 'High') and purpose == 'Browser cache/temp':
            return {
                'status': RecommendationStatus.CANDIDATE.value,
                'reasons': ['Matches recognized application temporary-cache rule.'],
                'evidence': ['Directory-based association (inferred)'],
                'errors': [],
            }

        if purpose in ('Browser cache/temp', 'Log file') and intel.get('confidence') == 'Low':
            return {
                'status': RecommendationStatus.REVIEW.value,
                'reasons': ['Purpose identified but confidence low.'],
                'evidence': [purpose],
                'errors': [],
            }

        return {
            'status': RecommendationStatus.UNKNOWN.value,
            'reasons': ['Insufficient evidence for confident cleanup recommendation.'],
            'evidence': [],
            'errors': [],
        }
