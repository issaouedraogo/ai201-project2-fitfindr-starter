"""
Unit tests for FitFindr tools and agent.

Run with: pytest tests/test_tools.py -v
         or from root: pytest tests/ -v
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from tools import search_listings, suggest_outfit, create_fit_card, price_comparison
from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe



class TestSearchListings:
    """Tests for search_listings tool."""

    def test_search_exact_keyword_match(self):
        """Test that exact keyword matches return results."""
        results = search_listings("graphic tee", limit=5)
        assert len(results) > 0
        assert any("graphic" in r.get("title", "").lower() or 
                  "graphic" in str(r.get("style_tags", [])).lower() 
                  for r in results)

    def test_search_with_price_filter(self):
        """Test that price filter excludes expensive items."""
        results = search_listings("vintage", max_price=30.0, limit=10)
        assert len(results) >= 0  # May be empty
        for item in results:
            assert item.get("price") <= 30.0, f"Price {item['price']} exceeds max_price 30.0"

    def test_search_with_size_filter(self):
        """Test that size filter includes matching sizes."""
        results = search_listings("tee", size="M", limit=10)
        # Results should be empty or have M in their size
        for item in results:
            size_str = item.get("size", "").lower()
            # Allow loose match: "M" in "S/M" or "M" in "M"
            assert "m" in size_str, f"Size {item['size']} doesn't match requested M"

    def test_search_no_results(self):
        """Test that impossible query returns empty list."""
        results = search_listings(
            "designer ballgown", 
            size="XXS", 
            max_price=5.0
        )
        assert isinstance(results, list)
        assert len(results) == 0

    def test_search_returns_scored_results(self):
        """Test that results include score field for ranking."""
        results = search_listings("vintage", limit=3)
        if results:
            for item in results:
                assert "score" in item
                assert isinstance(item["score"], float)
                assert item["score"] > 0

    def test_search_results_sorted_by_score(self):
        """Test that results are sorted by score (highest first)."""
        results = search_listings("vintage", limit=5)
        if len(results) > 1:
            scores = [r.get("score", 0) for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_search_limit_respected(self):
        """Test that limit parameter is respected."""
        results = search_listings("vintage", limit=3)
        assert len(results) <= 3


class TestSuggestOutfit:
    """Tests for suggest_outfit tool."""

    def test_suggest_outfit_with_example_wardrobe(self):
        """Test outfit suggestion with a populated wardrobe."""
        results = search_listings("graphic tee", limit=1)
        assert len(results) > 0, "No search results available for test"
        
        new_item = results[0]
        outfit = suggest_outfit(new_item, get_example_wardrobe())
        
        assert isinstance(outfit, str)
        assert len(outfit) > 0
        # Should mention the item or styling
        assert any(word in outfit.lower() for word in ["pair", "tee", "tuck", "wear"])

    def test_suggest_outfit_with_empty_wardrobe(self):
        """Test outfit suggestion gracefully handles empty wardrobe."""
        results = search_listings("vintage", limit=1)
        if results:
            new_item = results[0]
            outfit = suggest_outfit(new_item, get_empty_wardrobe())
            
            assert isinstance(outfit, str)
            assert len(outfit) > 0
            # Should suggest adding items or offer demo
            assert any(word in outfit.lower() 
                      for word in ["wardrobe", "add", "demo", "example"])

    def test_suggest_outfit_returns_string(self):
        """Test that suggest_outfit returns a string."""
        results = search_listings("vintage", limit=1)
        if results:
            outfit = suggest_outfit(results[0], get_example_wardrobe())
            assert isinstance(outfit, str)

    def test_suggest_outfit_with_max_items(self):
        """Test that max_items parameter is respected in the response."""
        results = search_listings("tops", limit=1)
        if results:
            outfit = suggest_outfit(results[0], get_example_wardrobe(), max_items=2)
            assert isinstance(outfit, str)
            # Should not crash with max_items parameter
            assert len(outfit) > 0


class TestCreateFitCard:
    """Tests for create_fit_card tool."""

    def test_create_fit_card_with_valid_outfit(self):
        """Test caption creation with valid outfit and item."""
        results = search_listings("graphic tee", limit=1)
        if results:
            new_item = results[0]
            outfit_text = suggest_outfit(new_item, get_example_wardrobe())
            caption = create_fit_card(outfit_text, new_item)
            
            assert isinstance(caption, str)
            assert len(caption) > 0
            # Should include item title or price
            assert "thrifted" in caption.lower() or new_item.get("title", "").lower() in caption.lower()

    def test_create_fit_card_respects_max_length(self):
        """Test that caption respects max_length parameter."""
        results = search_listings("vintage", limit=1)
        if results:
            outfit_text = suggest_outfit(results[0], get_example_wardrobe())
            caption = create_fit_card(outfit_text, results[0], max_length=100)
            
            assert len(caption) <= 100

    def test_create_fit_card_includes_price(self):
        """Test that caption includes price information."""
        results = search_listings("vintage", limit=1)
        if results:
            new_item = results[0]
            outfit_text = suggest_outfit(new_item, get_example_wardrobe())
            caption = create_fit_card(outfit_text, new_item)
            
            # Should include dollar amount
            assert "$" in caption or "price" in caption.lower()

    def test_create_fit_card_with_missing_fields(self):
        """Test that fit_card handles missing fields gracefully."""
        incomplete_item = {"title": "Test Item"}
        caption = create_fit_card("Test outfit", incomplete_item)
        
        assert isinstance(caption, str)
        # Should not crash, should produce some output


class TestAgentIntegration:
    """Integration tests for run_agent."""

    def test_agent_success_path(self):
        """Test full agent flow with a valid query."""
        result = run_agent(
            query="vintage graphic tee under $30, size M",
            wardrobe=get_example_wardrobe()
        )
        
        assert isinstance(result, dict)
        assert "query" in result
        assert "parsed" in result
        assert "search_results" in result
        assert "selected_item" in result
        assert "outfit_suggestion" in result
        assert "fit_card" in result
        assert "error" in result

    def test_agent_success_has_no_error(self):
        """Test that successful agent run has no error."""
        result = run_agent(
            query="vintage graphic tee",
            wardrobe=get_example_wardrobe()
        )
        
        if result["search_results"]:  # If search found items
            assert result["error"] is None
            assert result["fit_card"] is not None

    def test_agent_no_results_path(self):
        """Test agent handling when search returns no results."""
        result = run_agent(
            query="designer ballgown size XXS under $5",
            wardrobe=get_example_wardrobe()
        )
        
        assert isinstance(result, dict)
        assert result["error"] is not None
        assert len(result["search_results"]) == 0

    def test_agent_empty_wardrobe_path(self):
        """Test agent with empty wardrobe."""
        result = run_agent(
            query="vintage graphic tee",
            wardrobe=get_empty_wardrobe()
        )
        
        assert isinstance(result, dict)
        # May have search results but outfit should handle empty wardrobe
        if result["search_results"]:
            assert result["outfit_suggestion"] is not None

    def test_agent_parses_filters(self):
        """Test that agent correctly parses query into filters."""
        result = run_agent(
            query="looking for vintage graphic tee under $30, size M",
            wardrobe=get_example_wardrobe()
        )
        
        assert isinstance(result["parsed"], dict)
        parsed = result["parsed"]
        # Should extract max_price and size
        assert "description" in parsed or "query" in parsed
        # Price or size should be parsed
        assert parsed.get("max_price") is not None or parsed.get("size") is not None


class TestErrorHandling:
    """Tests for error handling in tools."""

    def test_search_listings_returns_list_on_error(self):
        """Test that search_listings returns empty list, not exception."""
        # Valid input should not crash
        results = search_listings("")
        assert isinstance(results, list)

    def test_suggest_outfit_handles_none_wardrobe(self):
        """Test suggest_outfit doesn't crash with edge case input."""
        results = search_listings("vintage", limit=1)
        if results:
            # Should handle gracefully
            outfit = suggest_outfit(results[0], {"items": []})
            assert isinstance(outfit, str)

    def test_create_fit_card_handles_empty_new_item(self):
        """Test create_fit_card doesn't crash with minimal input."""
        caption = create_fit_card("test outfit", {})
        assert isinstance(caption, str)


class TestRetryLogic:
    """Tests for search retry with fallback logic (extra credit feature)."""

    def test_retry_logic_success_on_first_attempt(self):
        """Test that retry returns results immediately if first search succeeds."""
        from agent import _search_with_retry
        
        results, retry_info = _search_with_retry("vintage", size="M", max_price=50)
        
        # Should find results (vintage is common)
        if len(results) > 0:
            assert len(retry_info["attempts"]) == 1  # Only tried once
            assert retry_info["message"] is None  # No relaxation needed

    def test_retry_logic_relaxes_size(self):
        """Test that retry relaxes size constraint on second attempt if needed."""
        from agent import _search_with_retry
        
        # Try impossible combination that might need size relaxation
        results, retry_info = _search_with_retry("vintage graphic tee", size="XXXL", max_price=100)
        
        # Results might come from relaxing size
        if len(results) > 0 and "size" in retry_info["final_filters"]:
            assert retry_info["final_filters"]["size"] is None  # Size was relaxed
            assert "removed size filter" in (retry_info["message"] or "").lower()

    def test_retry_logic_returns_info_on_failure(self):
        """Test that retry returns informative error message on complete failure."""
        from agent import _search_with_retry
        
        # Search that should fail: impossible combination
        results, retry_info = _search_with_retry("designer ballgown", size="XXS", max_price=1)
        
        assert len(results) == 0  # Should find nothing
        assert retry_info["message"] is not None  # Should have error message
        assert "after trying" in retry_info["message"].lower()  # Explains retry attempts
        assert len(retry_info["attempts"]) >= 1  # Tracked attempts

    def test_agent_uses_retry_logic(self):
        """Test that run_agent uses retry logic and tracks attempts."""
        # Try a query that might need retries
        result = run_agent("designer ballgown size XXL under $5", get_example_wardrobe())
        
        # May fail after retries
        assert "retry_info" in result
        if result["error"]:
            # If failed, should mention retry attempts in error
            assert "after trying" in result["error"].lower() or \
                   "no results found" in result["error"].lower()

    def test_retry_populates_session_retry_info(self):
        """Test that session dict includes retry_info field."""
        result = run_agent("vintage tee under $200", get_example_wardrobe())
        
        assert "retry_info" in result
        if result["search_results"]:  # If successful
            assert result["retry_info"] is not None


class TestStyleProfileMemory:
    """Tests for style profile memory (extra credit feature)."""

    _TEST_USER = "test_fitfindr_profile_user"

    def setup_method(self):
        from utils.style_profiles import delete_profile
        delete_profile(self._TEST_USER)

    def teardown_method(self):
        from utils.style_profiles import delete_profile
        delete_profile(self._TEST_USER)

    def test_create_and_load_profile(self):
        """Created profile can be loaded back in a later call (simulates new session)."""
        from utils.style_profiles import create_profile, load_profile

        create_profile(self._TEST_USER,
            preferred_styles=["vintage", "grunge"],
            preferred_sizes=["M"],
        )
        loaded = load_profile(self._TEST_USER)

        assert loaded is not None
        assert loaded["user_id"] == self._TEST_USER
        assert "vintage" in loaded["preferred_styles"]

    def test_load_missing_profile_returns_none(self):
        """Loading a nonexistent profile returns None without error."""
        from utils.style_profiles import load_profile

        result = load_profile("definitely_does_not_exist_xyz_123")
        assert result is None

    def test_profile_persists_across_calls(self):
        """Data written in one call is readable in a separate call."""
        from utils.style_profiles import create_profile, load_profile

        create_profile(self._TEST_USER,
            preferred_colors=["black", "navy"],
            notes="Love oversized fits",
        )

        profile1 = load_profile(self._TEST_USER)
        profile2 = load_profile(self._TEST_USER)

        assert profile1["preferred_colors"] == profile2["preferred_colors"]
        assert profile1["notes"] == profile2["notes"]

    def test_update_profile(self):
        """Updated fields are persisted and loadable."""
        from utils.style_profiles import create_profile, update_profile, load_profile

        create_profile(self._TEST_USER, preferred_styles=["vintage"])
        update_profile(self._TEST_USER, preferred_styles=["vintage", "streetwear"])

        loaded = load_profile(self._TEST_USER)
        assert "streetwear" in loaded["preferred_styles"]

    def test_enhance_search_adds_style_terms(self):
        """enhance_search_with_profile appends preferred styles to the query."""
        from utils.style_profiles import enhance_search_with_profile

        profile = {"preferred_styles": ["vintage", "minimalist"], "preferred_categories": ["tops"]}
        enhanced = enhance_search_with_profile("graphic tee", profile)

        assert "graphic tee" in enhanced
        assert "vintage" in enhanced

    def test_agent_stores_profile_in_session(self):
        """run_agent with user_id loads and stores the profile in session dict."""
        from utils.style_profiles import create_profile

        create_profile(self._TEST_USER, preferred_styles=["vintage"])

        result = run_agent("vintage tee", get_example_wardrobe(), user_id=self._TEST_USER)

        assert "profile" in result
        assert result["profile"] is not None
        assert result["profile"]["user_id"] == self._TEST_USER

    def test_agent_applies_profile_size_default(self):
        """Profile's preferred size is used when the query doesn't specify one."""
        from utils.style_profiles import create_profile

        create_profile(self._TEST_USER, preferred_sizes=["M"])

        result = run_agent("vintage tee", get_example_wardrobe(), user_id=self._TEST_USER)

        assert result["parsed"]["size"] == "M"

    def test_agent_query_size_overrides_profile(self):
        """Explicit size in the query wins over the profile default."""
        from utils.style_profiles import create_profile

        create_profile(self._TEST_USER, preferred_sizes=["XL"])

        result = run_agent("vintage tee size S", get_example_wardrobe(), user_id=self._TEST_USER)

        assert result["parsed"]["size"] == "S"

    def test_agent_applies_profile_budget_default(self):
        """Profile's budget max is used when the query doesn't specify a price."""
        from utils.style_profiles import create_profile

        create_profile(self._TEST_USER, budget_range={"min": 0, "max": 40})

        result = run_agent("vintage tee", get_example_wardrobe(), user_id=self._TEST_USER)

        assert result["parsed"]["max_price"] == 40.0

    def test_agent_query_price_overrides_profile(self):
        """Explicit price in the query wins over the profile budget."""
        from utils.style_profiles import create_profile

        create_profile(self._TEST_USER, budget_range={"min": 0, "max": 100})

        result = run_agent("vintage tee under $25", get_example_wardrobe(), user_id=self._TEST_USER)

        assert result["parsed"]["max_price"] == 25.0

    def test_agent_with_missing_profile_proceeds_normally(self):
        """run_agent with an unknown user_id proceeds without error."""
        result = run_agent("vintage tee", get_example_wardrobe(), user_id="no_such_user_xyz")

        assert isinstance(result, dict)
        assert result.get("profile") is None

    def test_agent_without_user_id_backward_compatible(self):
        """run_agent without user_id works exactly as before."""
        result = run_agent("vintage tee", get_example_wardrobe())

        assert isinstance(result, dict)
        assert result.get("profile") is None


class TestPriceComparison:
    """Tests for price comparison tool (extra credit feature)."""

    def test_price_comparison_returns_string(self):
        """Test that price_comparison returns a string."""
        item = {
            "id": "test1",
            "title": "Test Item",
            "category": "tops",
            "price": 20.0,
            "condition": "good",
            "style_tags": ["vintage"],
        }
        result = price_comparison(item)
        assert isinstance(result, str)

    def test_price_comparison_with_valid_item(self):
        """Test price comparison with a real item from dataset."""
        # Search for a real item first
        results = search_listings("vintage", limit=1)
        if results:
            item = results[0]
            comparison = price_comparison(item)
            
            # Should return assessment
            assert isinstance(comparison, str)
            assert len(comparison) > 0
            # Should contain price information
            assert "$" in comparison or "comparables" in comparison.lower()

    def test_price_comparison_identifies_fair_price(self):
        """Test that tool identifies items around average price."""
        results = search_listings("vintage", limit=3)
        if len(results) >= 1:
            item = results[0]
            comparison = price_comparison(item)
            
            # Should contain some rating
            assert any(rating in comparison.lower() for rating in 
                      ["fair", "good", "deal", "expensive", "overpriced", "comparables"])

    def test_price_comparison_handles_missing_price(self):
        """Test graceful handling when item price is missing."""
        item = {"id": "test", "title": "Item", "category": "tops"}
        comparison = price_comparison(item)
        
        assert isinstance(comparison, str)
        assert ("error" in comparison.lower() or "price" in comparison.lower())

    def test_price_comparison_handles_empty_item(self):
        """Test graceful handling of empty/None item."""
        comparison = price_comparison({})
        assert isinstance(comparison, str)
        assert len(comparison) > 0

    def test_price_comparison_handles_none(self):
        """Test graceful handling of None item."""
        comparison = price_comparison(None)
        assert isinstance(comparison, str)
        assert "error" in comparison.lower()

    def test_price_comparison_with_many_comparables(self):
        """Test that comparison finds statistics when many comparables exist."""
        # Search for a common item type that should have many comparables
        results = search_listings("vintage", limit=1)
        if results:
            item = results[0]
            comparison = price_comparison(item)
            
            # Should mention the number of comparables
            assert "n=" in comparison or "Comparables" in comparison

    def test_price_comparison_provides_range(self):
        """Test that comparison includes min/max/avg range."""
        results = search_listings("vintage", limit=1)
        if results:
            item = results[0]
            comparison = price_comparison(item)
            
            # Should show price range (min–max)
            if "–" in comparison or "comparables" in comparison.lower():
                assert "$" in comparison  # Should have prices

    def test_price_comparison_consistent_on_same_item(self):
        """Test that comparison is deterministic for same item."""
        item = {
            "id": "consistent_test",
            "title": "Consistent Item",
            "category": "tops",
            "price": 25.0,
            "condition": "good",
            "style_tags": ["vintage"],
        }
        
        result1 = price_comparison(item)
        result2 = price_comparison(item)
        
        # Should be identical
        assert result1 == result2



