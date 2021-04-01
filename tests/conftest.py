import json
import os
from os.path import join

import jwt
import pytest
from fastapi.testclient import TestClient

from gtr.constants import SECRET_KEY
from gtr.main import app
from gtr.recommender import Recommender


@pytest.fixture
def assert_all_responses_were_requested() -> bool:
    return False


@pytest.fixture(scope="session")
def token():
    return jwt.encode(
        {"user": "test", "group": "unlimited"}, SECRET_KEY, "HS256"
    ).decode("utf8")


@pytest.fixture(scope="session")
def default_token():
    return jwt.encode({"user": "test", "group": "default"}, SECRET_KEY, "HS256").decode(
        "utf8"
    )


@pytest.fixture(scope="session")
def invalid_token():
    return jwt.encode({"group": "unlimited"}, SECRET_KEY, "HS256").decode("utf8")


@pytest.fixture(scope="session")
def auth_header(token):
    return {"Authorization": "Bearer {}".format(token)}


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def data_path():
    return join(os.path.dirname(os.path.abspath(__file__)), "data")


@pytest.fixture(scope="session")
def song_dict(data_path):
    with open(join(data_path, "song.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def user_pyongs_dict(data_path):
    with open(join(data_path, "user_pyongs.json"), "r", encoding="utf8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def lastfm_track_toptags(data_path):
    with open(join(data_path, "lastfm_track_toptags.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def recommender():
    return Recommender()
