"""Provider-labeled ESPN ownership figures, matched only to unambiguous NFL players."""
import functools
import json
import math
import re
import time
from datetime import datetime, timezone
import requests
from modules import sleeper

TEAMS = {1:"ATL",2:"BUF",3:"CHI",4:"CIN",5:"CLE",6:"DAL",7:"DEN",8:"DET",9:"GB",10:"TEN",11:"IND",12:"KC",13:"LV",14:"LAR",15:"MIA",16:"MIN",17:"NE",18:"NO",19:"NYG",20:"NYJ",21:"PHI",22:"ARI",23:"PIT",24:"LAC",25:"SF",26:"SEA",27:"TB",28:"WAS",29:"CAR",30:"JAX",33:"BAL",34:"HOU"}
POSITIONS = {1:"QB",2:"RB",3:"WR",4:"TE"}


def normalized(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def source_url(season):
    return f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/3?view=kona_player_info"


@functools.lru_cache(maxsize=4)
def ownership_rows(season, bucket):
    filters = {"players":{"limit":1500,"sortPercOwned":{"sortPriority":1,"sortAsc":False},"filterStatsForTopScoringPeriodIds":{"value":1}}}
    try:
        with requests.get(source_url(season), headers={"X-Fantasy-Filter":json.dumps(filters)}, timeout=12, stream=True) as response:
            response.raise_for_status()
            raw = bytearray()
            for part in response.iter_content(65536):
                raw.extend(part)
                if len(raw) > 8_000_000:
                    return []
        payload = json.loads(raw)
        rows = []
        for entry in payload.get("players", [])[:1500]:
            player = entry.get("player", {})
            own = player.get("ownership") or {}
            rows.append({"id":str(player.get("id")),"name":normalized(player.get("fullName")),
                         "position":POSITIONS.get(player.get("defaultPositionId")),"team":TEAMS.get(player.get("proTeamId")),
                         "percent":own.get("percentOwned"),"at":own.get("date")})
        return rows
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return []


def roster_percentages(frame, now=None):
    now = now or time.time()
    season = sleeper.default_player_stats_season()
    rows = ownership_rows(season, int(now//1800))
    by_id = {row["id"]:row for row in rows}
    by_identity = {}
    for row in rows:
        by_identity.setdefault((row["name"],row["position"],row["team"]),[]).append(row)
    try:
        directory = sleeper.get_players()
    except Exception:
        directory = {}
    result = {}
    for _, player in frame.iterrows():
        pid = str(player.get("player_id"))
        name, position = normalized(player.get("name")), str(player.get("position"))
        record = by_id.get(str((directory.get(pid) or {}).get("espn_id")))
        if record is not None and (record["name"]!=name or record["position"]!=position):
            record = None
        if record is None:
            team = str(player.get("team"));team = "LAR" if team == "LA" else team
            matches = by_identity.get((name,position,team),[])
            if len(matches)==1:
                record = matches[0]
        if record is None:
            continue
        try:
            percent, stamp = float(record["percent"]), float(record["at"])
            if stamp > 10_000_000_000:
                stamp /= 1000
            if not math.isfinite(percent) or not 0<=percent<=100 or not -60<=now-stamp<=86400:
                continue
        except (TypeError,ValueError):
            continue
        result[pid] = {"percent":percent,"platform":"ESPN","league_format":"Fantasy football",
                       "source_url":source_url(season),"observed_at":datetime.fromtimestamp(stamp,timezone.utc).isoformat()}
    return result
