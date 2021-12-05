import os.path
import sys
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs

import chevron
import numpy as np
from google.cloud.firestore import ArrayRemove, Increment, SERVER_TIMESTAMP, Transaction, transactional
from google.cloud.firestore_v1.field_path import FieldPath

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.firebase import firestore
from utils.thompson import ThompsonSampling

# How many votes the prior votes count as
NUM_PRIOR_VOTES = 5

# Where Mustache templates are stored
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')

# Firestore schema information
METADATA_DOCUMENT_PATH = ('meta', 'meta')
CONTESTS_COLLECTION = 'contests'
USERS_COLLECTION = 'users'

# Which field each score increments
SCORE_UPDATES = {
    '1': 'observed_unfunny',
    '2': 'observed_somewhat_funny',
    '3': 'observed_funny',
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        db = firestore()
        users = db.collection(USERS_COLLECTION)

        try:
            cookies = SimpleCookie(self.headers.get('Cookie'))
            user_id = cookies['user_id'].value
            user_doc = users.document(user_id).get(('remaining_contests',))
            remaining_contests = user_doc.get('remaining_contests')
            if remaining_contests is None:
                raise ValueError('user does not exist')
        except (KeyError, ValueError):
            with open(os.path.join(TEMPLATE_DIR, 'welcome.html'), 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(f.read())
            return

        try:
            contest_ref = remaining_contests[0]
        except IndexError:
            with open(os.path.join(TEMPLATE_DIR, 'thanks.html'), 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(f.read())
            return

        contest_id = contest_ref.id
        contest_doc = contest_ref.get()
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
                         * NUM_PRIOR_VOTES / np.sum(prior_count) + 1)
        prior_failure = ((prior_unfunny + (prior_somewhat_funny * 0.5))
                         * NUM_PRIOR_VOTES / np.sum(prior_count) + 1)
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
            'contest_id': contest_id,
            'caption_id': caption_ndx,
            'caption': caption,
        }

        with open(os.path.join(TEMPLATE_DIR, 'index.mustache'), 'r') as f:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(chevron.render(f, data).encode('utf-8'))

    def do_POST(self):
        db = firestore()
        users = db.collection(USERS_COLLECTION)
        contests = db.collection(CONTESTS_COLLECTION)
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)
        cookies = SimpleCookie()

        try:
            parsed = parse_qs(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            parsed = {}

        if parsed.get('begin'):
            meta = db.document(*METADATA_DOCUMENT_PATH).get(('contests',))
            all_contests = meta.get('contests')

            user_ref = users.document()
            user_ref.create({
                'remaining_contests': all_contests,
                'votes': {},
            })

            cookies['user_id'] = user_ref.id
            cookies['user_id']['expires'] = 'Fri, 31 Dec 9999 23:59:59 GMT'
            cookies['user_id']['secure'] = True
            cookies['user_id']['httponly'] = True
            cookies['user_id']['samesite'] = 'Strict'

        else:
            try:
                cookies = SimpleCookie(self.headers.get('Cookie'))
                user_id = cookies['user_id'].value
                contest_id, = parsed['contest_id']
                caption_ndx, = parsed['caption_id']
                score, = parsed['score']
                update = SCORE_UPDATES[score]
            except (KeyError, ValueError):
                self.send_response(400)
                self.end_headers()
                return

            transaction = db.transaction()
            user_ref = users.document(user_id)
            contest_ref = contests.document(contest_id)
            vote_path = FieldPath('votes', contest_id).to_api_repr()
            count_update_path = FieldPath('summary', caption_ndx,
                                          'observed_count').to_api_repr()
            score_update_path = FieldPath('summary', caption_ndx,
                                          update).to_api_repr()

            @transactional
            def update_in_transaction(transaction: Transaction):
                user_doc = user_ref.get((vote_path,), transaction=transaction)
                try:
                    if user_doc.get(vote_path) is not None:
                        return
                except KeyError:
                    pass

                transaction.update(user_ref, {
                    'remaining_contests': ArrayRemove((contest_ref,)),
                    vote_path: {
                        'caption_id': caption_ndx,
                        'score': score,
                        'timestamp': SERVER_TIMESTAMP,
                    },
                })
                transaction.update(contest_ref, {
                    count_update_path: Increment(1),
                    score_update_path: Increment(1),
                })

            update_in_transaction(transaction)

        self.send_response(303)
        self.send_header('Location', self.path)
        for cookie in cookies.values():
            self.send_header('Set-Cookie', cookie.OutputString())
        self.end_headers()
