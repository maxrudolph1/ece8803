import itertools
import os
import re
import sys
from typing import Dict, Tuple, Union

import pandas as pd
from caption_contest_data import summary as get_summary, summary_ids
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.firebase import firestore

# Scores for each response
SCORES = {
    'funny': 3,
    'somewhat_funny': 2,
    'unfunny': 1,
}

# Possible algorithms to use for each contest
ALGORITHMS = (
    'thompson/beta',
    'thompson/triangle',
    'thompson/normal',
)

# How many of the top captions to use for each contest
NUM_TOP_CAPTIONS = 5

# What document stores the metadata for the entire app
METADATA_DOCUMENT_PATH = ('meta', 'meta')

# What collection to use for the output
OUTPUT_COLLECTION = 'contests'

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

# Some contests use the same comic. We want to merge these contests.
CONTEST_ID_MAPPINGS = {
    607: 605,
    645: 644,
    666: 665,
}


def get_contest_id(contest: Union[int, str]) -> int:
    '''Get the contest id from a summary id.

    >>> get_contest_id('516_summary_LilUCB.csv')
    516
    >>> get_contest_id(520)
    520
    '''
    if not isinstance(contest, int):
        contest = int(re.match(r'\d+', contest).group())
    return CONTEST_ID_MAPPINGS.get(contest, contest)


def get_comic(contest: Union[int, str]) -> Dict[str, Union[str, int]]:
    '''Based on [1] but not broken.

    [1] https://github.com/nextml/caption-contest-data/blob/c9d8c16b3f9a4030f2e6e0f87f8f8aeccfa34561/caption_contest_data/_api.py#L210-L243
    '''

    c = get_contest_id(contest)
    base = 'https://github.com/nextml/caption-contest-data/raw/master/contests/info'
    return base + f'/{c}/{c}.jpg'


def main():
    '''Write caption contest data to Firestore.'''

    contests_by_id = {}
    for contest in summary_ids():
        if contest not in EXCLUSIONS:
            contest_id = get_contest_id(contest)
            contests_by_id.setdefault(contest_id, []).append(contest)

    summaries = {}
    best_scores = {}
    for contest_id, contests in tqdm(contests_by_id.items()):
        df = pd.concat(get_summary(contest) for contest in contests)
        df = df[['funny', 'somewhat_funny', 'unfunny', 'count', 'caption']]
        groupby = df.groupby('caption')
        df = groupby.sum()

        df['score'] = sum(df[response] * score
                          for response, score in SCORES.items()) / df['count']
        df.sort_values('score', ascending=False, inplace=True)
        df = df.head(NUM_TOP_CAPTIONS)
        df.reset_index(inplace=True)
        best_score = df['score'].iloc[0]
        df.drop(columns=['score'], inplace=True)

        df.index = df.index.map(str)
        df.rename(columns={
            'funny': 'prior_funny',
            'somewhat_funny': 'prior_somewhat_funny',
            'unfunny': 'prior_unfunny',
            'count': 'prior_count',
        }, inplace=True)
        df[[
            'observed_funny',
            'observed_somewhat_funny',
            'observed_unfunny',
            'observed_count',
        ]] = 0

        summaries[contest_id] = df
        best_scores[contest_id] = best_score

    def sort_key(pair: Tuple[int, pd.DataFrame]) -> float:
        '''Sort by best score, descending.'''
        contest_id, summary = pair
        return -best_scores[contest_id]
    summaries = sorted(summaries.items(), key=sort_key)

    db = firestore()
    collection = db.collection(OUTPUT_COLLECTION)
    batch = db.batch()
    it = zip(summaries, itertools.cycle(ALGORITHMS))
    all_contests = []

    for (contest_id, summary), algorithm in it:
        contest_ref = collection.document(str(contest_id))
        batch.set(contest_ref, {
            'comic': get_comic(contest_id),
            'summary': summary.to_dict(orient='index'),
            'algorithm': algorithm,
        })
        all_contests.append(contest_ref)

    batch.set(db.document(*METADATA_DOCUMENT_PATH), {
        'contests': all_contests,
    })

    print(f'Writing {len(summaries)} contests to Firestore...')
    batch.commit()
    print('Done!')


if __name__ == '__main__':
    main()
