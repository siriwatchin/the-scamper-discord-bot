from kaggle.api.kaggle_api_extended import KaggleApi


def _get_api() -> KaggleApi:
    api = KaggleApi()
    api.authenticate()
    return api


def fetch_leaderboard(competition: str, page_size: int = 50) -> list[dict]:
    """Return leaderboard rows as a list of dicts with keys: rank, teamName, score."""
    api = _get_api()
    submissions = api.competition_leaderboard_view(competition, page_size=page_size)
    if not submissions:
        return []
    return [
        {"rank": i, "teamName": s.team_name, "score": str(s.score)}
        for i, s in enumerate(submissions, start=1)
    ]
