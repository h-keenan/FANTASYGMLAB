import pandas as pd


def apply_news_factor(df_players: pd.DataFrame) -> pd.DataFrame:
    """
    Stub for applying news impact to players.

    Later you can:
    - Pull RotoBaller/FantasyPros news feeds.
    - Map headlines to player names.
    - Compute a positive/negative news_factor per player.

    For now: everyone gets 0.0, but the column exists and flows into scoring.
    """
    df_players["news_factor"] = 0.0
    return df_players