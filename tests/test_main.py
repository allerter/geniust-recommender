from unittest.mock import create_autospec, patch

import lyricsgenius as lg
import pytest
import tekore as tk

from gtr.recommender import Preferences, Recommender


def get_mock_coro(return_value):
    async def mock_coro(*args, **kwargs):
        return return_value

    return mock_coro()


class TestAPI:
    def test_read_root(self, client, auth_header):
        response = client.get("/", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == {"status": "OK"}

    def test_artist(self, client, auth_header):
        artist_id = 1
        response = client.get(f"/artists/{artist_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["artist"]["id"] == artist_id

    def test_artist_missing_id(self, client, auth_header):
        artist_id = 99999999999
        response = client.get(f"/artists/{artist_id}", headers=auth_header)
        assert response.status_code == 404
        assert response.json().get("artist") is None

    def test_artists(self, client, auth_header):
        artist_ids = [1, 2, 3]
        response = client.get(
            "/artists",
            params={"ids": ",".join(str(x) for x in artist_ids)},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 200
        for i, artist_id in enumerate(artist_ids):
            assert response_dict["artists"][i]["id"] == artist_id

    def test_artists_bad_id_type(self, client, auth_header):
        artist_ids = [1, 2, "_3"]
        response = client.get(
            "/artists",
            params={"ids": ",".join(str(x) for x in artist_ids)},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 400
        assert response_dict.get("artists") is None

    def test_artists_over_limit(self, client, auth_header):
        artist_ids = [x for x in range(11)]
        response = client.get(
            "/artists",
            params={"ids": ",".join(str(x) for x in artist_ids)},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 400
        assert response_dict.get("artists") is None

    def test_artists_missing_id(self, client, auth_header):
        artist_ids = [1, 999999999999, 2]
        response = client.get(
            "/artists",
            params={"ids": ",".join(str(x) for x in artist_ids)},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 404
        assert response_dict.get("artists") is None

    def test_genres(self, client, auth_header, recommender):
        response = client.get("/genres", headers=auth_header)
        response_dict = response.json()
        assert response.status_code == 200
        assert len(response_dict["genres"]) == len(recommender.genres)

    def test_genres_with_age(self, client, auth_header, recommender):
        response = client.get("/genres", params={"age": 20}, headers=auth_header)
        response_dict = response.json()
        assert response.status_code == 200
        assert response_dict["genres"] == recommender.genres_by_age(20)

    @pytest.mark.parametrize("platform", ["genius", "spotify"])
    @pytest.mark.parametrize("result", [Preferences(genres=["pop"], artists=[]), None])
    def test_preferences_from_platform(self, client, auth_header, platform, result):
        recommender = create_autospec(Recommender)
        recommender.preferences_from_platform.return_value = result
        # Mock genius and spotify token responses
        if platform == "genius":
            OAuth2 = create_autospec(lg.OAuth2)
            OAuth2.get_user_token.return_value = "test_token"
            RefreshingCredentials = None
        else:
            RefreshingCredentials = create_autospec(tk.RefreshingCredentials)
            token = create_autospec(tk.RefreshingToken)
            token.access_token = "test_token"
            RefreshingCredentials.request_user_token.return_value = get_mock_coro(token)
            OAuth2 = None

        with patch("gtr.main.recommender", recommender), patch(
            "gtr.main.genius_auth", OAuth2
        ), patch("gtr.main.spotify_auth", RefreshingCredentials):
            response = client.get(
                "/preferences",
                params={f"{platform}_code": "test_code"},
                headers=auth_header,
            )
        response_dict = response.json()

        assert response.status_code == 200
        if result:
            assert response_dict["preferences"] == result
        else:
            assert response_dict["preferences"]["genres"] == []
            assert response_dict["preferences"]["artists"] == []

    def test_preferences_from_platform_no_code(self, client, auth_header):
        response = client.get("/preferences", headers=auth_header)
        response_dict = response.json()

        assert response.status_code == 400
        assert response_dict.get("preferences") is None

    @pytest.mark.parametrize("platform", ["genius", "spotify"])
    def test_preferences_from_platform_no_token(self, client, auth_header, platform):
        # Mock genius and spotify token responses
        if platform == "genius":
            OAuth2 = create_autospec(lg.OAuth2)
            OAuth2.get_user_token.return_value = None
            RefreshingCredentials = None
        else:
            RefreshingCredentials = create_autospec(tk.RefreshingCredentials)
            token = create_autospec(tk.RefreshingToken)
            token.access_token = None
            RefreshingCredentials.request_user_token.return_value = get_mock_coro(token)
            OAuth2 = None

        with patch("gtr.main.genius_auth", OAuth2), patch(
            "gtr.main.spotify_auth", RefreshingCredentials
        ):
            response = client.get(
                "/preferences",
                params={f"{platform}_code": "test_code"},
                headers=auth_header,
            )
        response_dict = response.json()

        assert response.status_code == 400
        assert response_dict.get("preferences") is None

    @pytest.mark.parametrize("artists", [None, "", "Eminem,Blackbear"])
    def test_recommendations(self, client, auth_header, artists):
        response = client.get(
            "/recommendations",
            params={"genres": "pop,rock", "artists": artists},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 200
        assert isinstance(response_dict["recommendations"], list)

    def test_recommendations_empty_genres(self, client, auth_header):
        response = client.get(
            "/recommendations",
            params={"genres": "", "artists": ""},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 400
        assert response_dict.get("recommendations") is None

    def test_recommendations_missing_genres(self, client, auth_header):
        response = client.get(
            "/recommendations", params={"artists": "Eminem"}, headers=auth_header
        )
        response_dict = response.json()
        assert response.status_code == 400
        assert response_dict.get("recommendations") is None

    def test_recommendations_invalid_genres(self, client, auth_header):
        response = client.get(
            "/recommendations",
            params={"genres": "invalid,pop", "artists": ""},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 400
        assert response_dict.get("recommendations") is None

    def test_recommendations_invalid_artists(self, client, auth_header):
        response = client.get(
            "/recommendations",
            params={"genres": "pop", "artists": "Eminem,invalid"},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 400
        assert response_dict.get("recommendations") is None

    def test_search_artist(self, client, auth_header):
        name = "Eminem"
        response = client.get(
            "/search/artists", params={"q": name}, headers=auth_header
        )
        response_dict = response.json()
        assert response.status_code == 200
        assert response_dict["hits"][0]["name"] == name

    def test_song(self, client, auth_header):
        song_id = 1
        response = client.get(f"/songs/{song_id}", headers=auth_header)
        response_dict = response.json()
        assert response.status_code == 200
        assert response_dict["song"]["id"] == song_id

    def test_song_missing_id(self, client, auth_header):
        song_id = 99999999999
        response = client.get(f"/songs/{song_id}", headers=auth_header)
        response_dict = response.json()
        assert response.status_code == 404
        assert response_dict.get("song") is None

    def test_songs(self, client, auth_header):
        song_ids = [1, 2, 3]
        response = client.get(
            "/songs",
            params={"ids": ",".join(str(x) for x in song_ids)},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 200
        for i, song_id in enumerate(song_ids):
            assert response_dict["songs"][i]["id"] == song_id

    def test_songs_missing_id(self, client, auth_header):
        song_ids = [1, 2, 99999999999]
        response = client.get(
            "/songs",
            params={"ids": ",".join(str(x) for x in song_ids)},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 404
        assert response_dict.get("songs") is None

    def test_songs_over_limit(self, client, auth_header):
        song_ids = [x for x in range(11)]
        response = client.get(
            "/songs",
            params={"ids": ",".join(str(x) for x in song_ids)},
            headers=auth_header,
        )
        response_dict = response.json()
        assert response.status_code == 400
        assert response_dict.get("songs") is None

    def test_len_songs(self, client, auth_header):
        response = client.get("/songs/len", headers=auth_header)
        response_dict = response.json()
        assert response.status_code == 200
        assert type(response_dict["len"]) is int

    def test_auth_in_query(self, client, token):
        response = client.get("/songs/len", params={"access_token": token})
        response_dict = response.json()
        assert response.status_code == 200
        assert type(response_dict["len"]) is int

    def test_missing_auth(self, client):
        response = client.get("/", headers=None)
        response_dict = response.json()
        assert type(response_dict) is dict
        assert response.status_code == 401

    @pytest.mark.parametrize(
        "auth_type", ["", "Bearer ", "Bearer _", "Bearer", "bearer "]
    )
    def test_invalid_auth(self, client, auth_type, invalid_token):
        response = client.get("/", headers={"Authorization": auth_type + invalid_token})
        response_dict = response.json()
        assert type(response_dict) is dict
        assert response.status_code == 401

    def test_too_many_requests(self, client, default_token):
        # limit for path "/" for default user group is 5/second
        for i in range(6):
            response = client.get(
                "/", headers={"Authorization": f"Bearer {default_token}"}
            )
            print("res: ", response.headers)
            if i < 5:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
