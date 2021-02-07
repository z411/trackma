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
    'season': None,
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


def test_late_subber_tag_with_hash_and_commas():
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
        releaseSource=["Web-DL"],
    )


def test_name_with_year():
    aie = AnimeInfoExtractor("[TestTag] Bungou Stray Dogs (2019) - 06 [496D45BB].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Bungou Stray Dogs (2019)",
        episodeStart=6,
        subberTag="TestTag",
        extension="mkv",
        hash="496D45BB",
    )


def test_name_with_year_and_extra_brackets():
    aie = AnimeInfoExtractor("[Erai-raws] Fairy Tail (2018) - 45 [1080p][Multiple Subtitle].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Fairy Tail (2018)",
        episodeStart=45,
        subberTag="Erai-raws",
        extension="mkv",
        resolution="1080p",
    )


def test_eac3():
    aie = AnimeInfoExtractor("[PAS] Houseki no Kuni - 05 [WEB 720p E-AC-3] [F671AE53].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Houseki no Kuni",
        episodeStart=5,
        subberTag="PAS",
        extension="mkv",
        resolution="720p",
        audioType=["E-AC-3"],
        releaseSource=["WEB"],
        hash="F671AE53",
    )


def test_with_episode_title():
    aie = AnimeInfoExtractor("[Opportunity] The Tatami Galaxy 10 - The 4.5-Tatami Idealogue [BD 720p] [FF757616].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="The Tatami Galaxy",
        episodeStart=10,
        subberTag="Opportunity",
        extension="mkv",
        resolution="720p",
        releaseSource=["BD"],
        hash="FF757616",
    )


def test_name_sXXeXX_and_sdtv():
    aie = AnimeInfoExtractor("Clannad - S02E01 - A Farewell to the End of Summer SDTV.mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Clannad 2",
        season=2,
        episodeStart=1,
        extension="mkv",
        resolution="SD",
        releaseSource=["TV"],
    )


def test_name_sXXeXX_and_trailing_hyphen():
    aie = AnimeInfoExtractor("ReZERO -Starting Life in Another World- S02E06 [1080p][E-AC3].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="ReZERO -Starting Life in Another World- 2",
        season=2,
        episodeStart=6,
        extension="mkv",
        resolution="1080p",
        audioType=["E-AC3"],
    )


def test_with_dots():
    aie = AnimeInfoExtractor("Kill.la.Kill.S01E01.1080p-Hi10p.BluRay.FLAC2.0.x264-CTR.[98AA9B1C].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Kill la Kill",
        season=1,
        episodeStart=1,
        extension="mkv",
        resolution="1080p",
        # releaseSource=["BluRay"],
        # audioType=["FLAC"],
        videoType=["H264", "Hi10P"],
        hash="98AA9B1C",
    )


def test_unusual_subber():
    aie = AnimeInfoExtractor("[-__-'] Girls und Panzer OVA 6 [BD 1080p FLAC] [B13C83A0].mkv")
    pprint(vars(aie))
    _assert_aie(
        aie,
        name="Girls und Panzer OVA",
        episodeStart=6,
        subberTag="-__-'",
        extension="mkv",
        resolution="1080p",
        releaseSource=["BD"],
        audioType=["FLAC"],
        hash="B13C83A0",
    )
