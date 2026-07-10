def age_penalty(position: str, age: float) -> int:
    if position == "RB":
        if age <= 27:
            return 0
        return int((age - 27) * 250)

    if position == "WR":
        if age <= 27:
            return 0
        return int((age - 27) * 150)

    if position == "TE":
        if age <= 28:
            return 0
        return int((age - 28) * 100)

    return 0