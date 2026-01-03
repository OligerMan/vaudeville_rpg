"""Elo rating system implementation."""

from dataclasses import dataclass


@dataclass
class RatingChange:
    """Result of a rating calculation."""

    winner_new_rating: int
    loser_new_rating: int
    winner_change: int
    loser_change: int


def calculate_expected_score(rating_a: int, rating_b: int) -> float:
    """Calculate expected score for player A against player B.

    Uses the standard Elo formula:
    E_A = 1 / (1 + 10^((R_B - R_A) / 400))

    Args:
        rating_a: Player A's current rating
        rating_b: Player B's current rating

    Returns:
        Expected score (0.0 to 1.0) for player A
    """
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def calculate_rating_change(
    winner_rating: int,
    loser_rating: int,
    k_factor: int = 32,
) -> RatingChange:
    """Calculate new ratings after a match.

    Uses standard Elo formula with configurable K-factor.
    Default K=32 is standard for new/casual players.

    Args:
        winner_rating: Winner's current rating
        loser_rating: Loser's current rating
        k_factor: Maximum rating change per game (default: 32)

    Returns:
        RatingChange with new ratings and changes
    """
    # Calculate expected scores
    winner_expected = calculate_expected_score(winner_rating, loser_rating)
    loser_expected = 1.0 - winner_expected

    # Winner gets score of 1, loser gets 0
    winner_change = round(k_factor * (1.0 - winner_expected))
    loser_change = round(k_factor * (0.0 - loser_expected))

    # Ensure minimum change of 1 for winner (prevents 0 change for big upsets)
    if winner_change == 0:
        winner_change = 1
    if loser_change == 0:
        loser_change = -1

    return RatingChange(
        winner_new_rating=winner_rating + winner_change,
        loser_new_rating=max(0, loser_rating + loser_change),  # Floor at 0
        winner_change=winner_change,
        loser_change=loser_change,
    )


def get_k_factor(rating: int, games_played: int = 0) -> int:
    """Get K-factor based on rating and experience.

    Higher K-factor = more volatile ratings (for new players).
    Lower K-factor = more stable ratings (for established players).

    Args:
        rating: Player's current rating
        games_played: Number of games played (optional)

    Returns:
        K-factor to use for rating calculations
    """
    # New players (fewer games) have higher K
    if games_played < 10:
        return 40

    # High-rated players have lower K for stability
    if rating >= 2000:
        return 16

    # Standard K for most players
    return 32
