# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from os.path import basename
import requests
import tempfile


def get_args(
    episode, show, player_path, types=["op", "ed", "mixed-op", "mixed-ed", "recap"]
):

    SUPPORTED_PLAYERS = ["mpv"]
    CHAPTERS_FILE_ARG = {"mpv": "--chapters-file"}
    ANI_SKIP_ENDPOINT = "https://api.aniskip.com/v2/skip-times/{idMal}/{episode}"

    player = basename(player_path)

    # Skip if the player does not support ffmetadata file
    if player not in SUPPORTED_PLAYERS:
        return None

    idMal = _idMal(show)

    if idMal is None:
        return None

    params = {"types": types, "episodeLength": 0}
    headers = {"accept": "application/json"}

    args = []

    try:
        response = requests.get(
            ANI_SKIP_ENDPOINT.format(idMal=idMal, episode=episode),
            params=params,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json().get("results")
            args.append(
                CHAPTERS_FILE_ARG[player] + "=" + _create_chapters_file(results)
            )

    except requests.RequestException as e:
        return None

    return "".join(args)


def _create_chapters_file(timestamps):
    """
    FFMetadata file generator
    Arguments: timestamps: list from ani-skip api
    Returns: Filename of the generated tmpfile

    https://api.aniskip.com/api-docs
    https://ffmpeg.org/ffmpeg-formats.html#metadata
    """

    CHAPTER_TYPES = {"op": "Opening", "ed": "Ending", "recap": "Recap"}
    TIMEBASE = "1/1000"

    chapters = [";FFMETADATA1"]

    episode_start = None
    episode_end = None

    for timestamp in timestamps:

        # If the skip type is not recognised, skip it
        if timestamp.get("skipType", None) not in CHAPTER_TYPES:
            continue

        start = int(float(timestamp["interval"]["startTime"]) * 1000)
        end = int(float(timestamp["interval"]["endTime"]) * 1000)
        title = CHAPTER_TYPES[timestamp["skipType"]]

        if title == CHAPTER_TYPES["op"]:
            episode_start = end
        elif title == CHAPTER_TYPES["ed"]:
            episode_end = start

        chapters.extend(
            [
                "[CHAPTER]",
                f"TIMEBASE={TIMEBASE}",
                f"START={start}",
                f"END={end}",
                f"TITLE={title}",
            ]
        )

    episode_content = [
        "[CHAPTER]",
        f"TIMEBASE={TIMEBASE}",
        "TITLE=Episode",
        f"START={episode_start if episode_start is not None else 0}",
    ]
    episode_content.append(
        f"END={episode_end if episode_end is not None else (episode_start if episode_start is not None else 0)}"
    )

    chapters.extend(episode_content)

    # Create a newline separated string from the built chapters list
    with tempfile.NamedTemporaryFile(
        delete=False, mode="w", encoding="utf-8"
    ) as tmp_file:
        tmp_file.write("\n".join(chapters) + "\n")
        tmp_filename = tmp_file.name

    return tmp_filename


def _idMal(show):
    return show.get("idMal", None)
