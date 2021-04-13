# GeniusT Recommender

> Genre-based music recommender

![status](https://img.shields.io/uptimerobot/status/m787655640-672a0fd52cb6b3f3a02aef57)
![GitHub release (latest by
date)](https://img.shields.io/github/v/release/allerter/geniust-recommender)
![build](https://github.com/allerter/geniust-recommender/workflows/build/badge.svg)
[![Test Coverage](https://api.codeclimate.com/v1/badges/175b7ad47144fe93c3df/test_coverage)](https://codeclimate.com/github/allerter/geniust-recommender/test_coverage)
[![Code style:
black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

GeniusT Recommender (GTR for short) is a genre-based recommender
with about 20K songs that half of them are Persian, and the other
half mostly English. The repo is also host to the REST API for the recommender.

## Recommender

GTR offers a basic genre-based music recommendation system that
offers users song recommendations from about 20K songs based on their
favorite genres and artists. Users can get their preferences from their
Genius or Spotify account or enter them manually. By logging into their
account through OAuth2, GeniusT will try to generate user's preferences
based on their account activity. If the user chooses to go the manual route,
they either input their age (and let the bot guess
the genres) or select them manually. Afterward, users can also add their
favorite artists from the available ones or finish without any favorite
artists (each user must have at least one favorite genre). Available
genres:

-   Classical
-   Country
-   Instrumental
-   Persian
-   Pop
-   Rap
-   R&B
-   Rock
-   Traditional

The *Persian* genre acts as a language parameter and a user with that
genre only gets songs that have the Persian genre; otherwise would get
non-Persian (mostly English) songs. The English songs were taken
randomly from the [LastFM 2020
dataset](https://github.com/renesemela/lastfm-dataset-2020). The Persian
songs are also retrieved from LastFM, but I neglected to save the
scripts I used to get the songs. Further information for songs was
retrieved from Spotify, Deezer, and Genius.

When a user\'s preferences are sent to the recommender, it will get all
songs that have one of the user\'s genres. Then the recommender chooses
a random subset of those songs to avoid sending the same songs each
time. Afterward, if the user had any favorite artists, the user
artists\' descriptions are compared with the subset songs artists\'
descriptions using TF-IDS to sort the songs based on the most
similarity. Then the 5 most similar songs will be returned.

All of the English songs have a preview URL, but because of copyright
laws have no download URL (full song URL). Although the users can
download the song from a link to another Telegram bot. Some Persian
songs have a preview URL and some a direct download URL for a 128-bit
MP3 file.


## API

The REST API has various methods and acts mainly as the interface for
the [GeniusT Telegram bot](https://github.com/allerter/geniust). The
API's auto-generated documentation is available at
[`/docs`](https://geniust-recommender.herokuapp.com/docs) and
[`/redoc`](https://geniust-recommender.herokuapp.com/redoc).

The API restricts and rate limits the requests and you need a Bearer token
in the Authorization header to access the endpoints. Alternatively you can
supply the token using the `access_token` query parameter which is
not as safe. Currently there is no way to register for a new token,
but you can use the test token to try out the API:

```bash
$TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoidGVzdCIsImdyb3VwIjoiZGVmYXVsdCJ9.d72_GIgfKkogHfjSHJS83DKVFK3jm8D9asN-wa-9vuU
curl -H "Authorization: Bearer $TOKEN" https://geniust-recommender.herokuapp.com/genres
```
