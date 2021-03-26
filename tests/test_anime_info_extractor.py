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


def _assert_aie(filename, **assertions):
    """Helper for asserting AnimeInfoExtractor results.

    Accepts a dict of assertions and asserts everything not provided as unchanged.
    """
    aie = AnimeInfoExtractor(filename)
    pprint(vars(aie))  # print defails for quicker debugging on failure
    for key, default in DEFAULTS.items():
        expected = assertions.get(key, default)
        assert getattr(aie, key) == expected
    return aie


def test_horriblesubs():
    filename = "[HorribleSubs] Nobunaga-sensei no Osanazuma - 04 [720p].mkv"
    aie = _assert_aie(
        filename,
        name="Nobunaga-sensei no Osanazuma",
        episodeStart=4,
        subberTag="HorribleSubs",
        extension="mkv",
        resolution="720p",
    )
    # check these only once
    assert aie.originalFilename == filename
    assert aie.getName() == "Nobunaga-sensei no Osanazuma"
    assert aie.getEpisode() == 4


def test_compound_subber_tag_and_wierd_epnum():
    _assert_aie(
        "[VCB-Studio+Commie] Sword Art Online II [03].mkv",
        name="Sword Art Online II",
        episodeStart=3,
        subberTag="VCB-Studio+Commie",
        extension="mkv",
    )


def test_late_subber_tag_with_hash_and_commas():
    _assert_aie(
        "Chio-chan no Tsuugakuro - 04 [HorribleSubs] [www, 720p, AAC] [5D4D1205].mkv",
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
    _assert_aie(
        "Arifureta E01v1 [1080p+][AAC][JapDub][GerSub][Web-DL].mkv",
        name="Arifureta",
        episodeStart=1,
        subberTag="JapDub",
        extension="mkv",
        resolution="1080p",
        audioType=["AAC"],
        releaseSource=["Web-DL"],
    )


def test_name_with_year():
    _assert_aie(
        "[TestTag] Bungou Stray Dogs (2019) - 06 [496D45BB].mkv",
        name="Bungou Stray Dogs (2019)",
        episodeStart=6,
        subberTag="TestTag",
        extension="mkv",
        hash="496D45BB",
    )


def test_name_with_year_and_extra_brackets():
    _assert_aie(
        "[Erai-raws] Fairy Tail (2018) - 45 [1080p][Multiple Subtitle].mkv",
        name="Fairy Tail (2018)",
        episodeStart=45,
        subberTag="Erai-raws",
        extension="mkv",
        resolution="1080p",
    )


def test_eac3():
    _assert_aie(
        "[PAS] Houseki no Kuni - 05 [WEB 720p E-AC-3] [F671AE53].mkv",
        name="Houseki no Kuni",
        episodeStart=5,
        subberTag="PAS",
        extension="mkv",
        resolution="720p",
        audioType=["E-AC-3"],
        releaseSource=["WEB"],
        hash="F671AE53",
    )


def test_with_number_in_episode_title():
    _assert_aie(
        "[Opportunity] The Tatami Galaxy 10 - The 4.5-Tatami Idealogue [BD 720p] [FF757616].mkv",
        name="The Tatami Galaxy",
        episodeStart=10,
        subberTag="Opportunity",
        extension="mkv",
        resolution="720p",
        releaseSource=["BD"],
        hash="FF757616",
    )


def test_with_standalone_number_in_episode_title():
    _assert_aie(
        "Monogatari - S02E01 - Karen Bee - Part 2.mkv",
        name="Monogatari 2",
        season=2,
        episodeStart=1,
        extension="mkv",
    )


def test_sXXeXX_and_sdtv():
    _assert_aie(
        "Clannad - S02E01 - A Farewell to the End of Summer SDTV.mkv",
        name="Clannad 2",
        season=2,
        episodeStart=1,
        extension="mkv",
        resolution="SD",
        releaseSource=["TV"],
    )


def test_sXXeXX_and_trailing_hyphen():
    _assert_aie(
        "ReZERO -Starting Life in Another World- S02E06 [1080p][E-AC3].mkv",
        name="ReZERO -Starting Life in Another World- 2",
        season=2,
        episodeStart=6,
        extension="mkv",
        resolution="1080p",
        audioType=["E-AC3"],
    )


def test_with_brackets():
    _assert_aie(
        "[HorribleSubs] Nakanohito Genome [Jikkyouchuu] - 01 [1080p].mkv",
        name="Nakanohito Genome",  # ' [Jikkyouchuu]' is stripped currently
        episodeStart=1,
        subberTag="HorribleSubs",
        extension="mkv",
        resolution="1080p",
    )


def test_with_dots():
    _assert_aie(
        "Kill.la.Kill.S01E01.1080p-Hi10p.BluRay.FLAC2.0.x264-CTR.[98AA9B1C].mkv",
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
    _assert_aie(
        "[-__-'] Girls und Panzer OVA 6 [BD 1080p FLAC] [B13C83A0].mkv",
        name="Girls und Panzer OVA",
        episodeStart=6,
        subberTag="-__-'",
        extension="mkv",
        resolution="1080p",
        releaseSource=["BD"],
        audioType=["FLAC"],
        hash="B13C83A0",
    )


def test_unusual_subber_and_no_epnum():
    _assert_aie(
        "[-__-'] Girls und Panzer OVA Anzio-sen [BD 1080p FLAC] [231FDA45].mkv",
        name="Girls und Panzer OVA Anzio-sen",
        subberTag="-__-'",
        extension="mkv",
        resolution="1080p",
        releaseSource=["BD"],
        audioType=["FLAC"],
        hash="231FDA45",
    )


def test_nothing_in_particular():
    _assert_aie(
        "[Underwater-FFF] Saki Zenkoku-hen - The Nationals - 01 [BD][1080p-FLAC][81722FD7].mkv",
        name="Saki Zenkoku-hen - The Nationals",
        episodeStart=1,
        subberTag="Underwater-FFF",
        extension="mkv",
        resolution="1080p",
        releaseSource=["BD"],
        audioType=["FLAC"],
        hash="81722FD7",
    )


def test_hi444pp_profile():
    _assert_aie(
        "[Erai-raws] Goblin Slayer - Goblin's Crown [BD][1080p YUV444P10][FLAC][Multiple Subtitle].mkv",
        name="Goblin Slayer - Goblin's Crown",
        subberTag="Erai-raws",
        extension="mkv",
        resolution="1080p",
        releaseSource=["BD"],
        audioType=["FLAC"],
        videoType=["H264", "Hi444PP"],
    )


def test_jpbd_lpcm():
    _assert_aie(
        "[Koten_Gars] Kiddy Grade - Movie I [JP.BD][Hi10][1080p][LPCM] [2FAAB41B].mkv",
        name="Kiddy Grade - Movie I",
        subberTag="Koten_Gars",
        extension="mkv",
        resolution="1080p",
        releaseSource=["BD"],
        audioType=["LPCM"],
        videoType=["H264", "Hi10P"],
        hash="2FAAB41B"
    )


def test_underscores():
    _assert_aie(
        "[No]Touhou_Gensou_Mangekyou_-_01_(Hi10P)[26D7A2B3].mkv",
        name="Touhou Gensou Mangekyou",
        episodeStart=1,
        subberTag="No",
        extension="mkv",
        videoType=["H264", "Hi10P"],
        hash="26D7A2B3"
    )


def test_literal_ep():
    _assert_aie(
        "Uzaki-chan wa Asobitai! Ep 2.mkv",
        name="Uzaki-chan wa Asobitai!",
        episodeStart=2,
        extension="mkv",
    )
