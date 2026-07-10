from typing import List, Dict


def trade_gain(send_players: List[Dict], receive_players: List[Dict]) -> int:
    send_value = 0
    receive_value = 0
    for p in send_players:
        send_value += int(p.get("score", p.get("value_score", 0)) or 0)
    for p in receive_players:
        receive_value += int(p.get("score", p.get("value_score", 0)) or 0)
    return receive_value - send_value
