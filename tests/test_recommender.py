from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest
from pytest_httpx import HTTPXMock

from gtr.recommender import Preferences


class TopArtists:
    Artist = namedtuple("Artist", "name")

    def __init__(self, artist_names):
        self.items = [self.Artist(name=name)
                      for name in artist_names]


class TopTracks:
    Track = namedtuple("Track", "name, artists")

    def __init__(self, track_names):
        self.items = [self.Track(name=name, artists=[name])
                      for name in track_names]


def get_mock_coro(return_value):
    async def mock_coro(*args, **kwargs):
        return return_value

    return mock_coro()


@pytest.fixture(scope="function")
def client(
    song_dict: dict,
    user_pyongs_dict: dict,
):
    top_tracks = TopTracks(["one", "two", "three"])
    top_artists = TopArtists(["Blackbear", "Eminem", "Unknown Artist"])
    client = MagicMock()
    client.PublicAPI().song.return_value = song_dict
    client.Genius().user_pyongs.return_value = user_pyongs_dict
    client.Spotify().current_user_top_tracks.return_value = get_mock_coro(top_tracks)
    client.Spotify().current_user_top_artists.return_value = get_mock_coro(top_artists)
    return client


class TestRecommender:
    @pytest.mark.parametrize("age", [0, 10, 20, 50, 70, 100])
    def test_genres_by_age(self, recommender, age):
        res = recommender.genres_by_age(age)

        assert isinstance(res, (list, tuple))
        for genre in res:
            assert genre in recommender.genres

    @pytest.mark.parametrize("artist", ["Eminem", "test", ""])
    def test_search_artist(self, recommender, artist):
        res = recommender.search_artist(artist)

        if artist == "Eminem":
            assert artist in [x.name for x in res]

    @pytest.mark.parametrize("genres", [[], ["pop", "rap"], ["persian"]])
    def test_binarize(self, recommender, genres):
        res = recommender.binarize(genres)

        assert sum(res) == len(genres)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("lastfm_200_response", [True, False])
    @pytest.mark.parametrize("platform", ["genius", "spotify"])
    async def test_preferences_from_platform(
        self,
        lastfm_track_toptags,
        lastfm_200_response,
        recommender,
        httpx_mock: HTTPXMock,
        client,
        platform,
    ):
        httpx_mock.add_response(
            json=lastfm_track_toptags if lastfm_200_response else {})
        token = "test_token"

        current_module = "gtr.recommender"
        with patch(current_module + ".tk", client), patch(
            current_module + ".lg", client
        ):
            await recommender.preferences_from_platform(token, platform)

    @pytest.mark.parametrize("genres", [["pop", "rap"], ["persian"]])
    @pytest.mark.parametrize("artists", [["Eminem"], []])
    @pytest.mark.parametrize(
        "song_type", ["any", "any_file", "preview", "full", "preview,full"]
    )
    def test_shuffle(self, recommender, genres, artists, song_type):
        preferences = Preferences(genres=genres, artists=artists)

        res = recommender.shuffle(preferences, song_type)

        for song in res:
            if song_type == "preview,full":
                assert song.download_url and song.preview_url
            elif song_type == "preview":
                assert song.preview_url
            elif song_type == "full":
                assert song.download_url
            has_user_genres = False
            for genre in genres:
                has_user_genres = genre in song.genres or has_user_genres
            assert has_user_genres
            if "persian" in genres:
                assert "persian" in song.genres
            else:
                assert "persian" not in song.genres

    def test_artist(self, recommender):
        artist_id = 1

        res = recommender.artist(id=1)

        assert res.id == artist_id

    def test_song(self, recommender):
        song_id = 1

        res = recommender.song(id=1)

        assert res.id == song_id

    def test_song_id_spotify(self, recommender):
        id_spotify = "0x7qAtKBfsMrtpohpw8wB0"

        res = recommender.song(id_spotify=id_spotify)

        assert res.id_spotify == id_spotify

    def test_song_no_id(self, recommender):
        with pytest.raises(AssertionError):
            recommender.song()
