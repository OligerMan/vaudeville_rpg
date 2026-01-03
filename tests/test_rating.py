"""Tests for the Elo rating system."""

import pytest

from vaudeville_rpg.utils.rating import (
    RatingChange,
    calculate_expected_score,
    calculate_rating_change,
    get_k_factor,
)


class TestExpectedScore:
    """Tests for expected score calculation."""

    def test_equal_ratings(self):
        """Equal ratings should give 0.5 expected score."""
        score = calculate_expected_score(1000, 1000)
        assert score == pytest.approx(0.5, abs=0.001)

    def test_higher_rated_player(self):
        """Higher rated player should have >0.5 expected score."""
        score = calculate_expected_score(1200, 1000)
        assert score > 0.5
        assert score < 1.0

    def test_lower_rated_player(self):
        """Lower rated player should have <0.5 expected score."""
        score = calculate_expected_score(1000, 1200)
        assert score < 0.5
        assert score > 0.0

    def test_400_rating_difference(self):
        """400 point difference gives ~0.91 expected score."""
        # Standard Elo: 400 points = 10x expected performance
        score = calculate_expected_score(1400, 1000)
        assert score == pytest.approx(0.909, abs=0.01)

    def test_symmetry(self):
        """Expected scores should sum to 1."""
        score_a = calculate_expected_score(1200, 1000)
        score_b = calculate_expected_score(1000, 1200)
        assert score_a + score_b == pytest.approx(1.0, abs=0.001)

    def test_large_rating_gap(self):
        """Very large gap should give score close to 1."""
        score = calculate_expected_score(2000, 1000)
        assert score > 0.99


class TestRatingChange:
    """Tests for rating change calculation."""

    def test_equal_ratings_winner_gains(self):
        """Winner should gain rating when ratings are equal."""
        result = calculate_rating_change(1000, 1000)
        assert result.winner_change > 0
        assert result.loser_change < 0

    def test_equal_ratings_symmetric_change(self):
        """Equal ratings should give symmetric changes."""
        result = calculate_rating_change(1000, 1000, k_factor=32)
        # With equal ratings, expected is 0.5, so change is K * 0.5 = 16
        assert result.winner_change == 16
        assert result.loser_change == -16

    def test_upset_winner_gains_more(self):
        """Lower rated winner should gain more than expected."""
        result = calculate_rating_change(800, 1200)
        # Winner was underdog, should gain more
        assert result.winner_change > 16  # More than equal-rating case

    def test_favorite_wins_gains_less(self):
        """Higher rated winner should gain less than expected."""
        result = calculate_rating_change(1200, 800)
        # Winner was favorite, should gain less
        assert result.winner_change < 16  # Less than equal-rating case

    def test_new_ratings_calculated_correctly(self):
        """New ratings should equal old + change."""
        result = calculate_rating_change(1000, 1000)
        assert result.winner_new_rating == 1000 + result.winner_change
        assert result.loser_new_rating == 1000 + result.loser_change

    def test_rating_floor_at_zero(self):
        """Rating should not go below zero."""
        # Very low rated loser against high rated winner
        result = calculate_rating_change(2000, 50)
        assert result.loser_new_rating >= 0

    def test_minimum_winner_change(self):
        """Winner should always gain at least 1 point."""
        # Huge favorite wins - would normally gain ~0
        result = calculate_rating_change(2500, 500)
        assert result.winner_change >= 1

    def test_minimum_loser_change(self):
        """Loser should always lose at least 1 point."""
        # Huge underdog loses - would normally lose ~0
        result = calculate_rating_change(500, 2500)
        assert result.loser_change <= -1

    def test_k_factor_affects_magnitude(self):
        """Higher K-factor should give larger changes."""
        result_low_k = calculate_rating_change(1000, 1000, k_factor=16)
        result_high_k = calculate_rating_change(1000, 1000, k_factor=32)
        assert result_high_k.winner_change > result_low_k.winner_change

    def test_returns_rating_change_dataclass(self):
        """Should return RatingChange dataclass."""
        result = calculate_rating_change(1000, 1000)
        assert isinstance(result, RatingChange)
        assert hasattr(result, 'winner_new_rating')
        assert hasattr(result, 'loser_new_rating')
        assert hasattr(result, 'winner_change')
        assert hasattr(result, 'loser_change')


class TestKFactor:
    """Tests for K-factor selection."""

    def test_new_player_high_k(self):
        """New players (few games) should have high K."""
        k = get_k_factor(1000, games_played=5)
        assert k == 40

    def test_standard_player(self):
        """Standard players should have K=32."""
        k = get_k_factor(1000, games_played=50)
        assert k == 32

    def test_high_rated_player_low_k(self):
        """High rated players should have low K for stability."""
        k = get_k_factor(2100, games_played=100)
        assert k == 16

    def test_default_games_played(self):
        """Default games_played (0) should give new player K."""
        k = get_k_factor(1000)
        # Default is 0 games, which is < 10, so new player K
        assert k == 40

    def test_boundary_new_player(self):
        """Player with exactly 10 games is no longer 'new'."""
        k_new = get_k_factor(1000, games_played=9)
        k_standard = get_k_factor(1000, games_played=10)
        assert k_new == 40
        assert k_standard == 32

    def test_boundary_high_rated(self):
        """Player at exactly 2000 rating gets low K."""
        k_standard = get_k_factor(1999, games_played=50)
        k_high = get_k_factor(2000, games_played=50)
        assert k_standard == 32
        assert k_high == 16


class TestRatingScenarios:
    """Integration tests for realistic rating scenarios."""

    def test_typical_match(self):
        """Test a typical close match."""
        # 1050 vs 950 - slight favorite wins
        result = calculate_rating_change(1050, 950)

        assert result.winner_new_rating > 1050
        assert result.loser_new_rating < 950
        # Changes should be reasonable (not extreme)
        assert 5 < result.winner_change < 20
        assert -20 < result.loser_change < -5

    def test_big_upset(self):
        """Test when underdog wins."""
        # 800 beats 1200 - major upset
        result = calculate_rating_change(800, 1200)

        # Underdog should gain a lot
        assert result.winner_change > 20
        # Favorite should lose a lot
        assert result.loser_change < -20

    def test_expected_result(self):
        """Test when favorite wins as expected."""
        # 1200 beats 800 - expected result
        result = calculate_rating_change(1200, 800)

        # Favorite should gain little
        assert result.winner_change < 12
        # Underdog should lose little
        assert result.loser_change > -12

    def test_rating_conservation_approximate(self):
        """Rating changes should approximately sum to zero."""
        # Note: Due to rounding and floor, not always exactly zero
        result = calculate_rating_change(1100, 900)
        total_change = result.winner_change + result.loser_change
        assert abs(total_change) <= 2  # Allow small rounding difference

    def test_multiple_matches_progression(self):
        """Test rating progression over multiple matches."""
        rating_a = 1000
        rating_b = 1000

        # A wins 3 in a row
        for _ in range(3):
            result = calculate_rating_change(rating_a, rating_b)
            rating_a = result.winner_new_rating
            rating_b = result.loser_new_rating

        # A should be significantly higher now
        assert rating_a > 1040
        assert rating_b < 960

        # Gap should increase each time A wins
        assert rating_a - rating_b > 80
