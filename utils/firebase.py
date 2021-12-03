import firebase_admin
import firebase_admin.credentials
import firebase_admin.firestore
import json
import os


def firebase() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        cert = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT'])
        cert = firebase_admin.credentials.Certificate(cert)
        return firebase_admin.initialize_app(credential=cert)


def firestore() -> firebase_admin.firestore.firestore.Client:
    return firebase_admin.firestore.client(firebase())
