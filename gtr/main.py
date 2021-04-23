import logging
import os
from typing import Callable, Dict, List, Optional, Type, Union

import httpx
import tekore as tk
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.openapi.utils import get_openapi
from ratelimit import Rule
from ratelimit.backends.redis import RedisBackend

from gtr.auth import CustomRateLimitMiddleware, create_jwt_auth, http_429_handler
from gtr.constants import HASH_ALGORITHM, REDIS_URL, SECRET_KEY
from gtr.recommender import (
    Artist,
    Preferences,
    Recommender,
    SimpleArtist,
    SimpleSong,
    Song,
    SongType,
)

# Set up logging
logger = logging.getLogger("gtr")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


def custom_openapi():
    """Add auth options to OpenAPI schema"""
    if app.openapi_schema:
        return app.openapi_schema
    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(dir_path, "VERSION"), "r") as f:
        verison = f.read().strip()
    openapi_schema = get_openapi(
        title="GTR Docs",
        version=verison,
        description="GeniusT Recommender API Documentation",
        routes=app.routes,
    )
    # define security options
    security_schemes = {
        "BearerAuth": {"type": "http", "scheme": "bearer"},
        "ApiKeyAuth": {"type": "apiKey", "in": "query", "name": "access_token"},
    }
    # add scurity schemes to global security schemes and individual routes
    openapi_schema["components"]["securitySchemes"] = security_schemes
    path_security_schemes = [{scheme: []} for scheme in security_schemes]
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = path_security_schemes

    # general info
    openapi_schema["info"]["contact"] = {
        "name": "GitHub Repository",
        "url": "https://github.com/allerter/geniust-recommender",
    }
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://github.com/allerter/geniust-recommender/blob/main/LICENSE",
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Get Redis credentials
redis_password, redis_socket = REDIS_URL.replace("redis://:", "").split("@")
redis_host, redis_port = redis_socket.split(":")
redis_port = int(redis_port)

app = FastAPI()
app.openapi = custom_openapi  # type: ignore

# Add rate limiting middleware
app.add_middleware(
    CustomRateLimitMiddleware,
    authenticate=create_jwt_auth(key=SECRET_KEY, algorithms=[HASH_ALGORITHM]),
    backend=RedisBackend(host=redis_host, port=redis_port, password=redis_password),
    config={
        r"^/$": [Rule(second=5, group="default"), Rule(group="unlimited")],
        r"^/genres.*": [Rule(second=5, group="default"), Rule(group="unlimited")],
        r"^/artists$": [Rule(second=2, group="default"), Rule(group="unlimited")],
        r"^/artists/[0-9]+$": [
            Rule(second=2, group="default"),
            Rule(group="unlimited"),
        ],
        r"^/preferences.*": [Rule(second=1, group="default"), Rule(group="unlimited")],
        r"^/recommendations.*": [
            Rule(second=2, group="default"),
            Rule(group="unlimited"),
        ],
        r"^/search/.*": [Rule(second=2, group="default"), Rule(group="unlimited")],
        r"^/songs/[0-9]+$": [Rule(second=3, group="default"), Rule(group="unlimited")],
        r"^/songs$": [Rule(second=2, group="default"), Rule(group="unlimited")],
        r"^/songs/len$": [Rule(second=2, group="default"), Rule(group="unlimited")],
    },
    on_blocked=http_429_handler,
)
recommender = Recommender()


def parse_list(
    param_name: str, type: Type[Union[int, str]], optional: bool = False
) -> Callable[..., Request]:
    def parse(request: Request):
        try:
            value = request.query_params[param_name]
            if value:
                return [type(x) for x in value.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Wrong item type. All items must be of type {type!r}",
            )
        except KeyError:
            if not optional:
                raise HTTPException(
                    status_code=400, detail=f"Missing parameter: {param_name!r}"
                )
        return []

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
        return {"artists": recommender.artists(ids=ids)}
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
    token: str,
    platform: str = Query(..., regex="^(spotify|genius)$"),
):
    """Get user preferences (genres and artists)
    based on user's activity on platform.
    """
    if platform == "genius":
        auth_header = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(headers=auth_header) as client:
            r = await client.get("https://api.genius.com/account")
            res = r.json()
            if r.status_code == 401:
                raise HTTPException(
                    status_code=400, detail="Invalid token. " + res["error_description"]
                )
    else:
        spotify = tk.Spotify(token, asynchronous=True)
        try:
            await spotify.current_user()
        except (tk.BadRequest, tk.Unauthorised) as e:  # pragma: no cover
            raise HTTPException(
                status_code=400,
                detail="Invalid token. " + e.response.content["error"]["message"],
            )
        await spotify.close()

    pref = await recommender.preferences_from_platform(token, platform)
    return {
        "preferences": pref if pref is not None else Preferences(genres=[], artists=[])
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
    artists: Optional[List[str]] = Depends(
        parse_list("artists", type=str, optional=True)
    ),
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


@app.get(
    "/search/songs",
    summary="Search songs",
    response_model=Dict[str, List[SimpleSong]],
    tags=["search"],
    response_description="List of Song objects",
)
def search_songs(q: str = Query(..., title="Song name", example="Rap God")):
    """Search recommender's songs."""
    return {"hits": recommender.search_song(q)}


@app.get(
    "/songs/len",
    summary="Number of songs in the recommender",
    response_model=Dict[str, int],
    tags=["songs"],
    response_description="Number of songs",
)
def len_songs():
    """Get the number of songs available in the recommender."""
    return {"len": recommender.num_songs}


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
def songs(ids: List[int] = Depends(parse_list("ids", type=int))):
    """Get more than one song using a comma-separated list.

    Limit: 10
    """
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="IDs can't be more than 10.")
    try:
        return {"songs": recommender.songs(ids)}
    except IndexError:
        raise HTTPException(status_code=404, detail="One of the song was not found")
