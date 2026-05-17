import io
import csv
import os
from kaggle.api.kaggle_api_extended import KaggleApiExtended


def _get_api() -> KaggleApiExtended:
    api = KaggleApiExtended()
    api.authenticate()
    return api


def fetch_leaderboard(competition: str) -> list[dict]:
    """Return leaderboard rows as a list of dicts with keys: rank, teamName, score."""
    api = _get_api()
    # Returns bytes of a zip containing a CSV
    result = api.competition_leaderboard_download(competition, path=None)
    import zipfile

    with zipfile.ZipFile(io.BytesIO(result)) as z:
        csv_name = z.namelist()[0]
        with z.open(csv_name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f))
            rows = list(reader)

    leaderboard = []
    for i, row in enumerate(rows, start=1):
        # Column names vary by competition; normalise common variants
        team = row.get("TeamName") or row.get("team_name") or row.get("Team Name") or ""
        score = row.get("Score") or row.get("score") or ""
        leaderboard.append({"rank": i, "teamName": team, "score": score})

    return leaderboard
