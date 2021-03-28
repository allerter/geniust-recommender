import logging
from typing import Dict, List, Optional

import tekore as tk
import lyricsgenius as lg
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request


from gtr.constants import (
    GENIUS_CLIENT_ID,
    GENIUS_CLIENT_SECRET,
    GENIUS_REDIRECT_URI,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)
from gtr.recommender import (
    Artist,
    Preferences,
    Recommender,
    SimpleArtist,
    Song,
    SongType,
)

logger = logging.getLogger("gtr")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

app = FastAPI()
recommender = Recommender()
genius_auth = lg.OAuth2.full_code_exchange(
    GENIUS_CLIENT_ID,
    GENIUS_REDIRECT_URI,
    GENIUS_CLIENT_SECRET,
    scope=("me", "vote"),
)
# print(lg.OAuth2(client_id="asd", client_secret="asd", redirect_uri="asd"))
# exit()
spotify_auth = tk.RefreshingCredentials(
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)


def parse_list(param_name: str, type):
    def parse(request: Request):
        try:
            value = request.query_params[param_name]
            if value:
                return [type(x) for x in value.split(",")]
            return []
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Wrong item type. All items must be of type {type!r}",
            )
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Missing parameter: {param_name!r}"
            )

    return parse


@app.get("/", response_model=Dict[str, str])
def read_root():
    return {"status": "OK"}


@app.get(
    "/artists/{id}",
    summary="Get artist",
    response_model=Dict[str, Artist],
    tags=["artists"],
    response_description="Artist object",
)
def artist(
    id: int = Path(
        ...,
        title="Artist ID",
        example=1,
    )
):
    """Get an artist by ID"""
    try:
        return {"artist": recommender.artist(id=id)}
    except IndexError:
        raise HTTPException(status_code=404, detail="Artist not found")


@app.get(
    "/artists",
    summary="Get several artists",
    response_model=Dict[str, List[Artist]],
    tags=["artists"],
    response_description="List of Artist objects",
)
def artists(ids: List[int] = Depends(parse_list("ids", type=int))):
    """Get more than one artist using a comma-separated list.

    Limit: 10
    """
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="IDs can't be more than 10.")
    try:
        return {"artists": [recommender.artist(id=id) for id in ids]}
    except IndexError:
        raise HTTPException(status_code=404, detail="One of the artists was not found.")


@app.get(
    "/genres",
    summary="Get genres",
    tags=["genres"],
    response_model=Dict[str, List[str]],
    response_description="List of genres",
)
def genres(
    age: Optional[int] = Query(
        None,
        title="User age",
        description="Returns a list of genres based on the user's age group",
        ge=0,
        le=100,
        example=20,
    )
):
    """Get recommender's available genres.

    You can also get a user's genres based on their
    age group by supplying the age parameter.
    """
    if age:
        genres = recommender.genres_by_age(age)
    else:
        genres = recommender.genres
    return {"genres": genres}


@app.get(
    "/preferences",
    summary="Get preferences from music plaltforms",
    tags=["preferences"],
    response_model=Dict[str, Preferences],
    response_description="Preferences object",
)
async def preferences_from_platform(
    genius_code: Optional[str] = None, spotify_code: Optional[str] = None
):
    """Get user preferences (genres and artists)
    based on user's activity on platform.
    """
    if not any((genius_code, spotify_code)):
        raise HTTPException(
            status_code=400,
            detail="No code provided.",
        )
    elif genius_code:
        token = genius_auth.get_user_token(code=genius_code)
        platform = "genius"
    else:
        token = await spotify_auth.request_user_token(spotify_code)
        token = token.access_token
        platform = "spotify"

    if token is None:
        raise HTTPException(
            status_code=400,
            detail="Failed to get the token.",
        )
    else:
        pref = await recommender.preferences_from_platform(token, platform)
        return {
            "preferences": pref
            if pref is not None
            else Preferences(genres=[], artists=[])
        }


@app.get(
    "/recommendations",
    summary="Get song recommendations",
    response_model=Dict[str, List[Song]],
    tags=["recommendations"],
    response_description="List of Song objects",
)
def recommend(
    genres: List[str] = Depends(parse_list("genres", type=str)),
    artists: List[str] = Depends(parse_list("artists", type=str)),
    song_type: SongType = SongType.any,
):
    """Get recommender's genres or get a user's genres based on age.

    - **genres**: A comma-separated list of genres.
    - **artists**: A comma-separated list of artists (optional).
    - **song_type**: The type of the song. For example, "preview"
    means that the song must have a preview link.
    """
    # genres must be valid
    if not genres:
        raise HTTPException(
            status_code=400,
            detail="Genres can't be empty.",
        )
    invalid_genre = None
    for genre in genres:
        if genre not in recommender.genres:
            invalid_genre = genre
            break
    if invalid_genre:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid genre in genres: {invalid_genre!r}",
        )

    # artists must be valid
    if artists:
        invalid_artist = None
        for request_artist in artists:
            if request_artist not in recommender.artists_names:
                invalid_artist = request_artist
                break
        if invalid_artist:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid artist in artists: {invalid_artist!r}",
            )

    user_preferences = Preferences(genres=genres, artists=artists)
    return {
        "recommendations": recommender.shuffle(
            user_preferences, song_type=song_type.value
        )
    }


@app.get(
    "/search/artists",
    summary="Search artists",
    response_model=Dict[str, List[SimpleArtist]],
    tags=["search"],
    response_description="List of SimpleArtist objects",
)
def search_artists(q: str = Query(..., title="Artist name", example="Eminem")):
    """Search recommender's artists."""
    return {"hits": recommender.search_artist(q)}


# @app.get(
#    "/search/songs",
#    summary="Search songs",
#    response_model=Dict[str, List[Song]],
#    tags=["search"],
#    response_description="List of Song objects",
# )
# def search_songs(q: str = Query(..., title="Song name", example="Rap God")):
#    """Search recommender's songs."""
#    return {"hits": recommender.search_song(q)}


@app.get(
    "/songs/{id}",
    summary="Get a song",
    response_model=Dict[str, Song],
    tags=["songs"],
    response_description="Song object",
)
def song(
    id: int = Path(
        ...,
        title="Song ID",
        example=1,
    )
):
    """Get a song by ID."""
    try:
        return {"song": recommender.song(id=id)}
    except IndexError:
        raise HTTPException(status_code=404, detail="Song not found")


@app.get(
    "/songs",
    summary="Get several songs",
    response_model=Dict[str, List[Song]],
    tags=["songs"],
    response_description="List of Song objects",
)
def songs(ids=Depends(parse_list("ids", type=int))):
    """Get more than one song using a comma-separated list.

    Limit: 10
    """
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="IDs can't be more than 10.")
    try:
        return {"songs": [recommender.song(id=id) for id in ids]}
    except IndexError:
        raise HTTPException(status_code=404, detail="One of the song was not found")
