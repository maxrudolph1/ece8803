import os.path
import random
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs

import chevron
import numpy as np
from google.cloud.firestore import Increment, SERVER_TIMESTAMP

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.firebase import firestore
from utils.thompson import ThompsonSampling

# What to normalize Thompson sampling priors to
NORMALIZE_PRIORS_TO = 2.0

# Where Mustache templates are stored
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')

# Firestore schema information
METADATA_DOCUMENT_PATH = ('meta', 'meta')
CONTESTS_COLLECTION = 'contests'
VOTES_COLLECTION = 'votes'

# Which field each score increments
SCORE_UPDATES = {
    '1': 'observed_unfunny',
    '2': 'observed_somewhat_funny',
    '3': 'observed_funny',
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        db = firestore()
        num_contests = (db.document(*METADATA_DOCUMENT_PATH)
                        .get(('num_contests',)).get('num_contests'))
        contest_ndx = random.randrange(num_contests)
        contest_doc = (db.collection(CONTESTS_COLLECTION)
                       .document(str(contest_ndx)).get())

        contest_id = contest_doc.get('contest_id')
        comic = contest_doc.get('comic')
        summary = contest_doc.get('summary')
        algorithm = contest_doc.get('algorithm')

        n_arms = len(summary)
        (
            prior_funny,
            prior_somewhat_funny,
            prior_unfunny,
            prior_count,
            observed_funny,
            observed_somewhat_funny,
            observed_unfunny,
            observed_count,
        ) = (
            np.array([summary[str(i)][column] for i in range(n_arms)])
            for column in (
                'prior_funny',
                'prior_somewhat_funny',
                'prior_unfunny',
                'prior_count',
                'observed_funny',
                'observed_somewhat_funny',
                'observed_unfunny',
                'observed_count',
            )
        )

        prior_success = ((prior_funny + (prior_somewhat_funny * 0.5))
                         * NORMALIZE_PRIORS_TO / np.sum(prior_count) + 1)
        prior_failure = ((prior_unfunny + (prior_somewhat_funny * 0.5))
                         * NORMALIZE_PRIORS_TO / np.sum(prior_count) + 1)
        observed_success = observed_funny + (observed_somewhat_funny * 0.5)
        observed_failure = observed_unfunny + (observed_somewhat_funny * 0.5)

        if algorithm == 'thompson/beta':
            thompson = ThompsonSampling(
                n_arms,
                prior_success=prior_success,
                prior_failure=prior_failure,
                observed_success=observed_success,
                observed_failure=observed_failure,
                dist='beta',
            )
            caption_ndx = thompson.select_arm()
        elif algorithm == 'thompson/triangle':
            thompson = ThompsonSampling(
                n_arms,
                prior_success=prior_success,
                prior_failure=prior_failure,
                observed_success=observed_success,
                observed_failure=observed_failure,
                dist='triangle',
            )
            caption_ndx = thompson.select_arm()
        elif algorithm == 'thompson/normal':
            thompson = ThompsonSampling(
                n_arms,
                prior_success=prior_success,
                prior_failure=prior_failure,
                observed_success=observed_success,
                observed_failure=observed_failure,
                dist='normal',
            )
            caption_ndx = thompson.select_arm()
        else:
            raise ValueError(f'Unknown algorithm for contest: {contest_id}')

        caption = summary[str(caption_ndx)]['caption']
        data = {
            'comic': comic,
            'contest_id': contest_ndx,
            'caption_id': caption_ndx,
            'caption': caption,
        }

        with open(os.path.join(TEMPLATE_DIR, 'index.mustache'), 'r') as f:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(chevron.render(f, data).encode('utf-8'))

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)

        try:
            parsed = parse_qs(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            parsed = {}

        try:
            contest_ndx, = parsed['contest_id']
            caption_ndx, = parsed['caption_id']
            score, = parsed['score']
            update = SCORE_UPDATES[score]
        except (KeyError, ValueError):
            self.send_response(400)
            self.end_headers()
            return

        db = firestore()
        db.collection(VOTES_COLLECTION).document().create({
            'contest_id': contest_ndx,
            'caption_id': caption_ndx,
            'score': score,
            'ip_address': self.headers.get('X-Forwarded-For', ''),
            'timestamp': SERVER_TIMESTAMP,
        })
        db.collection(CONTESTS_COLLECTION).document(contest_ndx).update({
            f'summary.{caption_ndx!s}.{update}': Increment(1),
            f'summary.{caption_ndx!s}.observed_count': Increment(1),
        })

        self.send_response(303)
        self.send_header('Location', self.path)
        self.end_headers()
