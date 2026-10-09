import time
import pandas as pd
from modules import public_roster_percentages as public


def test_identity_and_population_are_preserved_and_missing_is_not_zero(monkeypatch):
    now=time.time()
    rows=[{"id":"11","name":"playerone","position":"WR","team":"BUF","percent":0,"at":now*1000},
          {"id":"12","name":"playertwo","position":"RB","team":"CLE","percent":35.2,"at":(now-90000)*1000}]
    monkeypatch.setattr(public,"ownership_rows",lambda *a:rows)
    monkeypatch.setattr(public.sleeper,"get_players",lambda:{})
    monkeypatch.setattr(public.sleeper,"default_player_stats_season",lambda:2026)
    frame=pd.DataFrame([{"player_id":"1","name":"Player One","position":"WR","team":"BUF"},{"player_id":"2","name":"Player Two","position":"RB","team":"CLE"},{"player_id":"3","name":"Unknown","position":"WR","team":"BUF"}])
    result=public.roster_percentages(frame,now)
    assert result["1"]["percent"]==0 and result["1"]["platform"]=="ESPN"
    assert "2" not in result and "3" not in result
    monkeypatch.setattr(public,"ownership_rows",lambda *a:rows+[rows[0]])
    assert public.roster_percentages(frame,now)=={}
