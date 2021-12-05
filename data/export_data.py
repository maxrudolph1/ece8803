import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.firebase import firestore

# Collections to export
COLLECTIONS = (
    'votes',
)


def main():
    db = firestore()
    for collection_name in COLLECTIONS:
        collection = db.collection(collection_name)
        with open(f'{collection_name}.jsonl', 'w') as f:
            for doc in collection.stream():
                json.dump(doc.to_dict(), f, default=repr, indent=2)
                f.write('\n')
        print('Exported all documents in collection {}'.format(collection_name))


if __name__ == '__main__':
    main()
