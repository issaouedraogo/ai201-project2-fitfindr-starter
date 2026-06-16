"""
Style Profile Management — Remember user style preferences across sessions.

Allows users to create and persist style profiles with preferred colors, styles,
categories, sizes, and budget. Profiles are stored as JSON and can be loaded
to automatically enhance searches and outfit suggestions.

Usage:
    from utils.style_profiles import create_profile, load_profile, enhance_search_with_profile
    
    # Create a profile
    profile = create_profile("user_123", 
        preferred_colors=["black", "navy"], 
        preferred_styles=["vintage", "minimalist"],
        preferred_categories=["tops", "outerwear"],
        budget_range={"min": 10, "max": 50}
    )
    
    # Load and use profile later
    profile = load_profile("user_123")
    enhanced_query = enhance_search_with_profile("graphic tee", profile)
    # Result: "graphic tee vintage minimalist" (adds style preferences)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any


PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


def _ensure_profiles_dir():
    """Create profiles directory if it doesn't exist."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _profile_path(user_id: str) -> Path:
    """Get the file path for a user's profile."""
    return PROFILES_DIR / f"{user_id}.json"


def create_profile(
    user_id: str,
    preferred_colors: List[str] | None = None,
    preferred_styles: List[str] | None = None,
    preferred_categories: List[str] | None = None,
    preferred_sizes: List[str] | None = None,
    budget_range: Dict[str, float] | None = None,
    notes: str = "",
) -> dict:
    """
    Create and save a new style profile for a user.
    
    Args:
        user_id: Unique user identifier
        preferred_colors: List of preferred color names (e.g., ["black", "navy"])
        preferred_styles: List of preferred style tags (e.g., ["vintage", "minimalist"])
        preferred_categories: List of preferred item categories (e.g., ["tops", "shoes"])
        preferred_sizes: List of preferred sizes (e.g., ["M", "L"])
        budget_range: Dict with "min" and "max" price (e.g., {"min": 10, "max": 50})
        notes: Additional user notes (e.g., "Love oversized fits")
    
    Returns:
        The created profile dict.
    """
    _ensure_profiles_dir()
    
    profile = {
        "user_id": user_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "preferred_colors": preferred_colors or [],
        "preferred_styles": preferred_styles or [],
        "preferred_categories": preferred_categories or [],
        "preferred_sizes": preferred_sizes or [],
        "budget_range": budget_range or {},
        "notes": notes,
    }
    
    # Save to file
    path = _profile_path(user_id)
    try:
        with open(path, "w") as f:
            json.dump(profile, f, indent=2)
    except Exception as e:
        return {"error": f"Failed to save profile: {str(e)}"}
    
    return profile


def load_profile(user_id: str) -> Optional[dict]:
    """
    Load a user's style profile from disk.
    
    Args:
        user_id: User identifier
    
    Returns:
        Profile dict if found, None otherwise.
    """
    path = _profile_path(user_id)
    
    if not path.exists():
        return None
    
    try:
        with open(path, "r") as f:
            profile = json.load(f)
        return profile
    except Exception as e:
        return None


def update_profile(user_id: str, **updates) -> Optional[dict]:
    """
    Update specific fields of a user's profile.
    
    Args:
        user_id: User identifier
        **updates: Fields to update (e.g., preferred_colors=[...], notes="...")
    
    Returns:
        Updated profile dict, or None if profile not found.
    """
    profile = load_profile(user_id)
    if not profile:
        return None
    
    # Update allowed fields
    allowed_fields = {
        "preferred_colors", "preferred_styles", "preferred_categories",
        "preferred_sizes", "budget_range", "notes"
    }
    
    for key, value in updates.items():
        if key in allowed_fields:
            profile[key] = value
    
    profile["updated_at"] = datetime.now().isoformat()
    
    # Save updated profile
    _ensure_profiles_dir()
    path = _profile_path(user_id)
    try:
        with open(path, "w") as f:
            json.dump(profile, f, indent=2)
    except Exception:
        return None
    
    return profile


def delete_profile(user_id: str) -> bool:
    """
    Delete a user's profile.
    
    Args:
        user_id: User identifier
    
    Returns:
        True if deleted, False otherwise.
    """
    path = _profile_path(user_id)
    if not path.exists():
        return False
    
    try:
        path.unlink()
        return True
    except Exception:
        return False


def get_all_profiles() -> List[dict]:
    """
    Get all saved style profiles.
    
    Returns:
        List of profile dicts.
    """
    _ensure_profiles_dir()
    profiles = []
    
    for profile_file in PROFILES_DIR.glob("*.json"):
        try:
            with open(profile_file, "r") as f:
                profile = json.load(f)
                profiles.append(profile)
        except Exception:
            pass
    
    return profiles


def enhance_search_with_profile(query: str, profile: dict) -> str:
    """
    Augment a search query with user's style profile preferences.
    
    Adds preferred styles and categories to the query to personalize results.
    
    Args:
        query: Original user query
        profile: Style profile dict from load_profile()
    
    Returns:
        Enhanced query string with style preferences added.
    """
    if not profile:
        return query
    
    enhancements = []
    
    # Add style preferences
    if profile.get("preferred_styles"):
        enhancements.extend(profile["preferred_styles"][:2])  # Top 2 styles
    
    # Add category if not already mentioned
    if profile.get("preferred_categories"):
        enhancements.append(profile["preferred_categories"][0])
    
    if enhancements:
        enhanced = f"{query} {' '.join(enhancements)}"
    else:
        enhanced = query
    
    return enhanced.strip()


def get_profile_summary(profile: dict) -> str:
    """
    Get a human-readable summary of a user's style profile.
    
    Args:
        profile: Style profile dict
    
    Returns:
        Summary string.
    """
    if not profile:
        return "No profile found."
    
    summary_parts = []
    
    if profile.get("preferred_colors"):
        summary_parts.append(f"Colors: {', '.join(profile['preferred_colors'])}")
    
    if profile.get("preferred_styles"):
        summary_parts.append(f"Styles: {', '.join(profile['preferred_styles'])}")
    
    if profile.get("preferred_categories"):
        summary_parts.append(f"Categories: {', '.join(profile['preferred_categories'])}")
    
    if profile.get("preferred_sizes"):
        summary_parts.append(f"Sizes: {', '.join(profile['preferred_sizes'])}")
    
    if profile.get("budget_range"):
        budget = profile["budget_range"]
        if budget.get("min") is not None and budget.get("max") is not None:
            summary_parts.append(f"Budget: ${budget['min']:.0f}–${budget['max']:.0f}")
    
    if profile.get("notes"):
        summary_parts.append(f"Notes: {profile['notes']}")
    
    return "\n".join(summary_parts) if summary_parts else "Empty profile"
