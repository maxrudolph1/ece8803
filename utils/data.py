import re
from typing import Dict, Union
from caption_contest_data import summary, summary_ids

# We want to exclude any contests that asked a question besides "how funny is
# this caption?"
# See https://nextml.github.io/caption-contest-data/contest-basics.html#queries
EXCLUSIONS = {
    # asked "which of these two captions is funnier?"
    '508-round2_summary_RoundRobin.csv',
    '509-round2_summary_RoundRobin.csv',

    # asked "how original is this caption?"
    '560_summary_KLUCB_original.csv',
}


def get_contest_id(contest: Union[int, str]) -> int:
    '''Get the contest id from a summary id.

    >>> get_contest_id('516_summary_LilUCB.csv')
    516
    >>> get_contest_id(520)
    520
    '''
    if isinstance(contest, int):
        return contest
    return int(re.match(r'\d+', contest).group())


def metadata(contest: Union[int, str]) -> Dict[str, Union[str, int]]:
    '''Based on [1] but not broken.

    [1] https://github.com/nextml/caption-contest-data/blob/c9d8c16b3f9a4030f2e6e0f87f8f8aeccfa34561/caption_contest_data/_api.py#L210-L243
    '''

    c = get_contest_id(contest)
    df = summary(contest)
    base = "https://github.com/nextml/caption-contest-data/raw/master/contests/info"
    top = df["rank"].idxmin()

    d = {
        "comic": base + f"/{c}/{c}.jpg",
        "num_responses": df["count"].sum(),
        "num_captions": len(df["caption"]),
        "funniest_caption": df.loc[top, "caption"],
    }
    if c not in {519, 550, 587, 588}:
        d.update({"example_query": base + f"/{c}/example_query.png"})
    return d