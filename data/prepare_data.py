import itertools
import os
import re
import sys
from typing import Dict, Union

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
NUM_TOP_CAPTIONS = 20

# How many contests to use
NUM_CONTESTS = 12

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


def get_comic(contest: Union[int, str]) -> Dict[str, Union[str, int]]:
    '''Based on [1] but not broken.

    [1] https://github.com/nextml/caption-contest-data/blob/c9d8c16b3f9a4030f2e6e0f87f8f8aeccfa34561/caption_contest_data/_api.py#L210-L243
    '''

    c = get_contest_id(contest)
    base = 'https://github.com/nextml/caption-contest-data/raw/master/contests/info'
    return base + f'/{c}/{c}.jpg'


def main():
    '''Write caption contest data to Firestore.'''

    db = firestore()
    collection = db.collection(OUTPUT_COLLECTION)

    contests_by_id = {}
    for contest in summary_ids():
        if contest not in EXCLUSIONS:
            contest_id = get_contest_id(contest)
            contests_by_id.setdefault(contest_id, []).append(contest)

    batch = db.batch()
    it = enumerate(zip(contests_by_id.items(), itertools.cycle(ALGORITHMS)))
    it_len = len(contests_by_id)
    for i, ((contest_id, contests), algorithm) in tqdm(it, total=it_len):
        df = pd.concat(get_summary(contest) for contest in contests)
        df = df[['funny', 'somewhat_funny', 'unfunny', 'count', 'caption']]
        groupby = df.groupby('caption')
        df = groupby.sum()

        df['score'] = sum(df[response] * score
                          for response, score in SCORES.items()) / df['count']
        df.sort_values('score', ascending=False, inplace=True)
        df = df.head(NUM_TOP_CAPTIONS)
        df.reset_index(inplace=True)
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

        batch.set(collection.document(str(i)), {
            'contest_id': contest_id,
            'comic': get_comic(contest_id),
            'summary': df.to_dict(orient='index'),
            'algorithm': algorithm,
        })

    batch.set(db.document(*METADATA_DOCUMENT_PATH), {
        'num_contests': len(contests_by_id),
    })

    print(f'Writing {len(contests_by_id)} contests to Firestore...')
    batch.commit()
    print('Done!')


if __name__ == '__main__':
    main()
