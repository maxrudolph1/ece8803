import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.firebase import firestore

# Collections to delete
COLLECTIONS = (
    'meta',
    'contests',
    'users',
)


def main():
    db = firestore()
    for collection_name in COLLECTIONS:
        collection = db.collection(collection_name)
        while True:
            docs = collection.list_documents()
            batch = None
            for doc in docs:
                if batch is None:
                    batch = db.batch()
                batch.delete(doc)
            if batch is None:
                break
            batch.commit()
        print('Deleted all documents in collection {}'.format(collection_name))


if __name__ == '__main__':
    main()
