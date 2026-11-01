"""NFL stadium table for weather lookups: nflverse ``stadium_id`` -> location
and roof kind.

Keyed by the same ``stadium_id`` that nflverse's games.csv publishes for every
game (including not-yet-played ones), so neutral-site games (London, Munich,
Mexico City, ...) resolve to their real venue rather than the home team's
usual one.

Roof kinds:

- ``outdoor``: open air. Weather applies.
- ``dome``: fixed roof (or a canopy that blocks precipitation and wind).
  Weather is ignored.
- ``retractable``: the roof state is not known before kickoff (and these
  venues close the roof in bad weather as a rule), so weather is treated as
  unknown and no adjustment is made.

Coordinates are stadium-level (rounded to ~100 m); that is far finer than the
forecast grid they are used with.
"""

from __future__ import annotations

from typing import NamedTuple


class Stadium(NamedTuple):
    lat: float
    lon: float
    roof: str  # "outdoor" | "dome" | "retractable"


STADIUMS: dict[str, Stadium] = {
    "ATL00": Stadium(33.757, -84.401, "dome"),
    "ATL97": Stadium(33.755, -84.401, "retractable"),
    "BAL00": Stadium(39.278, -76.623, "outdoor"),
    "BOS00": Stadium(42.091, -71.264, "outdoor"),
    "BUF00": Stadium(42.774, -78.787, "outdoor"),
    "BUF01": Stadium(43.641, -79.389, "retractable"),
    "CAR00": Stadium(35.226, -80.853, "outdoor"),
    "CHI98": Stadium(41.862, -87.617, "outdoor"),
    "CIN00": Stadium(39.095, -84.516, "outdoor"),
    "CLE00": Stadium(41.506, -81.699, "outdoor"),
    "DAL00": Stadium(32.748, -97.093, "retractable"),
    "DEN00": Stadium(39.744, -105.020, "outdoor"),
    "DET00": Stadium(42.340, -83.046, "dome"),
    "FRA00": Stadium(50.069, 8.645, "outdoor"),
    "GER00": Stadium(48.219, 11.625, "outdoor"),
    "GNB00": Stadium(44.501, -88.062, "outdoor"),
    "HOU00": Stadium(29.685, -95.411, "retractable"),
    "IND00": Stadium(39.760, -86.164, "retractable"),
    "JAX00": Stadium(30.324, -81.637, "outdoor"),
    "KAN00": Stadium(39.049, -94.484, "outdoor"),
    "LAX01": Stadium(33.953, -118.339, "dome"),
    "LAX97": Stadium(33.864, -118.261, "outdoor"),
    "LAX99": Stadium(34.014, -118.288, "outdoor"),
    "LON00": Stadium(51.556, -0.280, "outdoor"),
    "LON01": Stadium(51.456, -0.341, "outdoor"),
    "LON02": Stadium(51.604, -0.066, "outdoor"),
    "MAD01": Stadium(40.453, -3.688, "retractable"),
    "MEL00": Stadium(-37.820, 144.983, "retractable"),
    "MEX00": Stadium(19.303, -99.150, "outdoor"),
    "MIA00": Stadium(25.958, -80.239, "outdoor"),
    "MIN00": Stadium(44.974, -93.258, "dome"),
    "MIN01": Stadium(44.974, -93.257, "dome"),
    "MIN98": Stadium(44.976, -93.224, "outdoor"),
    "MUN01": Stadium(48.219, 11.625, "retractable"),
    "NAS00": Stadium(36.166, -86.771, "outdoor"),
    "NOR00": Stadium(29.951, -90.081, "dome"),
    "NYC01": Stadium(40.814, -74.074, "outdoor"),
    "OAK00": Stadium(37.752, -122.201, "outdoor"),
    "PAR00": Stadium(48.924, 2.360, "outdoor"),
    "PHI00": Stadium(39.901, -75.168, "outdoor"),
    "PHO00": Stadium(33.528, -112.263, "retractable"),
    "PIT00": Stadium(40.447, -80.016, "outdoor"),
    "RIO00": Stadium(-22.912, -43.230, "outdoor"),
    "SAO00": Stadium(-23.545, -46.474, "outdoor"),
    "SDG00": Stadium(32.783, -117.120, "outdoor"),
    "SEA00": Stadium(47.595, -122.332, "outdoor"),
    "SFO00": Stadium(37.714, -122.386, "outdoor"),
    "SFO01": Stadium(37.403, -121.970, "outdoor"),
    "STL00": Stadium(38.633, -90.189, "dome"),
    "TAM00": Stadium(27.976, -82.503, "outdoor"),
    "VEG00": Stadium(36.091, -115.184, "dome"),
    "WAS00": Stadium(38.908, -76.864, "outdoor"),
}


def stadium_for(stadium_id: str | None) -> Stadium | None:
    """The stadium for an nflverse stadium_id, or None when unknown."""

    if not stadium_id:
        return None
    return STADIUMS.get(str(stadium_id).strip().upper())


# Each franchise's regular home venue (current). Neutral-site and
# international games (London, Munich, Madrid, Mexico City, Sao Paulo, ...)
# are NOT looked up here: the real venue comes from the game's own
# ``stadium_id`` in nflverse's games.csv, so they resolve through STADIUMS.
# SoFi (LAR/LAC) has a fixed canopy over open sides; it is treated as a dome.
HOME_STADIUM_BY_TEAM: dict[str, str] = {
    "ARI": "PHO00", "ATL": "ATL97", "BAL": "BAL00", "BUF": "BUF00",
    "CAR": "CAR00", "CHI": "CHI98", "CIN": "CIN00", "CLE": "CLE00",
    "DAL": "DAL00", "DEN": "DEN00", "DET": "DET00", "GB": "GNB00",
    "HOU": "HOU00", "IND": "IND00", "JAX": "JAX00", "KC": "KAN00",
    "LV": "VEG00", "LAC": "LAX01", "LAR": "LAX01", "MIA": "MIA00",
    "MIN": "MIN01", "NE": "BOS00", "NO": "NOR00", "NYG": "NYC01",
    "NYJ": "NYC01", "PHI": "PHI00", "PIT": "PIT00", "SF": "SFO01",
    "SEA": "SEA00", "TB": "TAM00", "TEN": "NAS00", "WAS": "WAS00",
}
