from modules import my_news, news_signal

ITEM = {
    "title": "NC State To Hire Philip Rivers As HC",
    "summary": "Russell Wilson, another former Wolfpack passer, also interviewed for the job, hire",
    "link": "https://example.com/a",
}


def test_other_first_name_detected():
    assert news_signal.other_first_name_before_surname("Michael Wilson", ITEM["summary"])
    assert not news_signal.other_first_name_before_surname("Russell Wilson", ITEM["summary"])
    assert not news_signal.other_first_name_before_surname("Michael Wilson", "Michael Wilson was hurt")
    assert not news_signal.other_first_name_before_surname("Michael Wilson", "Wilson was hurt in practice")


def test_not_tagged_to_wrong_wilson():
    assert my_news.filter_news_for_players([ITEM], ["Michael Wilson"]) == []
