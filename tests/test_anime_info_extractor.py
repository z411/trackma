from pprint import pprint

# import pytest

from trackma.extras import AnimeInfoExtractor

DEFAULTS = {
    'resolution': '',
    'hash': '',
    'subberTag': '',
    'videoType': [],
    'audioType': [],
    'releaseSource': [],
    'extension': '',
    'episodeStart': None,
    'episodeEnd': None,
    'volumeStart': None,
    'volumeEnd': None,
    'version': 1,
    'name': '',
    'pv': -1,
}


def _assert_aie(aie, **assertions):
    """Helper for asserting AnimeInfoExtractor results.

    Accepts a dict of assertions and asserts everything not provided as unchanged.
    """
    for key, default in DEFAULTS.items():
        expected = assertions.get(key, default)
        assert getattr(aie, key) == expected


def test_horriblesubs():
    name = "[HorribleSubs] Nobunaga-sensei no Osanazuma - 04 [720p].mkv"
    aie = AnimeInfoExtractor(name)
    _assert_aie(
        aie,
        name="Nobunaga-sensei no Osanazuma",
        episodeStart=4,
        subberTag="HorribleSubs",
        extension="mkv",
        resolution="720p",
    )
    # check these only once
    assert aie.originalFilename == name
    assert aie.getName() == "Nobunaga-sensei no Osanazuma"
    assert aie.getEpisode() == 4


def test_compound_subber_tag_and_wierd_epnum():
    aie = AnimeInfoExtractor("[VCB-Studio+Commie] Sword Art Online II [03].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Sword Art Online II",
        episodeStart=3,
        subberTag="VCB-Studio+Commie",
        extension="mkv",
    )


def test_late_subber_tag_with_hash():
    aie = AnimeInfoExtractor("Chio-chan no Tsuugakuro - 04 [HorribleSubs] [www, 720p, AAC] [5D4D1205].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Chio-chan no Tsuugakuro",
        episodeStart=4,
        subberTag="HorribleSubs",
        extension="mkv",
        resolution="720p",
        audioType=["AAC"],
        hash="5D4D1205",
        releaseSource=["www"],
    )


def test_dubsub():
    aie = AnimeInfoExtractor("Arifureta E01v1 [1080p+][AAC][JapDub][GerSub][Web-DL].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Arifureta",
        episodeStart=1,
        subberTag="JapDub",
        extension="mkv",
        resolution="1080p",
        audioType=["AAC"],
        releaseSource=["WEB"],
    )
