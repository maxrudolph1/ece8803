import os
import re
import sys
from typing import Dict, Union

from caption_contest_data import summary as get_summary, summary_ids
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.firebase import firestore

# What document stores the metadata for the entire app
METADATA_DOCUMENT_PATH = ('meta', 'meta')

# What collection to use for the output
OUTPUT_COLLECTION = 'contests'

# Summary columns of interest
SUMMARY_COLUMNS = ['funny', 'somewhat_funny', 'unfunny']

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


def get_metadata(contest: Union[int, str]) -> Dict[str, Union[str, int]]:
    '''Based on [1] but not broken.

    [1] https://github.com/nextml/caption-contest-data/blob/c9d8c16b3f9a4030f2e6e0f87f8f8aeccfa34561/caption_contest_data/_api.py#L210-L243
    '''

    c = get_contest_id(contest)
    df = get_summary(contest)
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


def main():
    '''Write caption contest data to Firestore.'''

    db = firestore()
    collection = db.collection(OUTPUT_COLLECTION)

    contests_by_id = {}
    for contest in summary_ids():
        if contest not in EXCLUSIONS:
            contest_id = get_contest_id(contest)
            contests_by_id.setdefault(contest_id, []).append(contest)

    for i, (contest_id, contests) in enumerate(tqdm(contests_by_id.items())):
        document = {
            'contest_id': contest_id,
            'comic': None,
            'num_responses': 0,
            'num_captions': 0,
            'summary': {},
            'subcontests': [],
        }

        for contest in contests:
            metadata = get_metadata(contest)
            document['comic'] = metadata['comic']
            document['num_responses'] += int(metadata['num_responses'])
            document['num_captions'] += metadata['num_captions']

            summary = get_summary(contest)
            for record in summary[SUMMARY_COLUMNS].to_dict(orient='records'):
                document['summary'][str(len(document['summary']))] = record

            document['subcontests'].append({
                'contest': contest,
                'num_captions': metadata['num_captions'],
            })

        collection.document(str(i)).set(document)

    db.document(*METADATA_DOCUMENT_PATH).set({
        'num_contests': len(contests_by_id),
    })


if __name__ == '__main__':
    main()
