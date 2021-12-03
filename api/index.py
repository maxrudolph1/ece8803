import os.path
import random
import sys
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs

import caption_contest_data._api as caption_contest_data_api
from caption_contest_data import summary as get_summary
from chevron import render
from google.cloud.firestore import Increment, SERVER_TIMESTAMP

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.firebase import firestore
from utils.thompson import ThompsonSampling

# Where Mustache templates are stored
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')

# Firestore schema information
METADATA_DOCUMENT_PATH = ('meta', 'meta')
CONTESTS_COLLECTION = 'contests'
VOTES_COLLECTION = 'votes'

# Which field each score increments
SCORE_UPDATES = {
    '0': 'unfunny',
    '1': 'somewhat_funny',
    '2': 'funny',
}


def without_ccd_cache(ccd_func):
    def wrapper(*args, **kwargs):
        with tempfile.TemporaryDirectory() as temp_dir:
            caption_contest_data_api._root = Path(temp_dir)
            return ccd_func(*args, **kwargs)
    return wrapper


get_summary = without_ccd_cache(get_summary)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        db = firestore()
        num_contests = (db.document(*METADATA_DOCUMENT_PATH)
                        .get(('num_contests',)).get('num_contests'))
        contest_ndx = random.randrange(num_contests)
        contest_doc = (db.collection(CONTESTS_COLLECTION)
                       .document(str(contest_ndx)).get())

        n_arms = contest_doc.get('num_captions')
        summary = contest_doc.get('summary')

        num_funny = [summary[str(i)]['funny'] for i in range(n_arms)]
        num_somewhat_funny = [summary[str(i)]['somewhat_funny']
                              for i in range(n_arms)]
        num_unfunny = [summary[str(i)]['unfunny'] for i in range(n_arms)]
        total_votes = contest_doc.get('num_responses')

        # Perform Thompson sampling to select a caption
        alphas = [caption_num_funny + 1 for caption_num_funny in num_funny]
        betas = [caption_num_unfunny + 1 for caption_num_unfunny in num_unfunny]
        thompson = ThompsonSampling(n_arms, alphas, betas)
        caption_ndx = thompson.select_arm()

        caption_ndx_acc = caption_ndx
        caption = None
        for subcontest in contest_doc.get('subcontests'):
            num_captions = subcontest['num_captions']
            if caption_ndx_acc < num_captions:
                captions = get_summary(subcontest['contest'])['caption']
                caption = captions.iat[caption_ndx_acc]
                break
            caption_ndx_acc -= num_captions

        data = {
            'comic': contest_doc.get('comic'),
            'contest_id': contest_ndx,
            'caption_id': caption_ndx,
            'caption': caption,
        }

        with open(os.path.join(TEMPLATE_DIR, 'index.mustache'), 'r') as f:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(render(f, data).encode('utf-8'))

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
            'num_responses': Increment(1),
            f'summary.{caption_ndx!s}.{update}': Increment(1),
        })

        self.send_response(303)
        self.send_header('Location', self.path)
        self.end_headers()
