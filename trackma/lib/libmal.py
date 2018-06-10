# -*- coding: utf-8 -*-
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

import re
import urllib.parse
import urllib.request
import datetime
import base64
import gzip
import xml.etree.ElementTree as ET

from trackma.lib.lib import lib
from trackma import utils

class libmal(lib):
    """
    API class to communicate with MyAnimeList
    Should inherit a base library interface.

    Website: http://www.myanimelist.net
    API documentation: https://myanimelist.net/modules.php?go=api
    Designed by: Garrett Gyssler (https://myanimelist.net/profile/Xinil)

    """
    name = 'libmal'

    username = '' # TODO Must be filled by check_credentials
    logged_in = False
    opener = None

    api_info =  { 'name': 'MyAnimeList', 'shortname': 'mal', 'version': '', 'merge': False }

    default_mediatype = 'anime'
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_tag': True,
        'can_update': True,
        'can_play': True,
        'can_date': True,
        'status_start': 1,
        'status_finish': 2,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
        'score_max': 10,
        'score_step': 1,
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_tag': True,
        'can_update': True,
        'can_play': False,
        'can_date': True,
        'status_start': 1,
        'status_finish': 2,
        'statuses': [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Reading', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Read' },
        'score_max': 10,
        'score_step': 1,
    }

    # Authorized User-Agent for Trackma
    url = 'https://myanimelist.net/api/'
    useragent = 'api-team-f894427cc1c571f79da49605ef8b112f'

    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        # Since MyAnimeList uses a cookie we just create a HTTP Auth handler
        # together with the urllib opener.
        super(libmal, self).__init__(messenger, account, userconfig)

        token = '%s:%s' % (account['username'], account['password'])
        auth_string = 'Basic ' + base64.b64encode(token.encode('utf-8')).decode('ascii').replace('\n', '')

        self.username = self._get_userconfig('username')
        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [
            ('User-Agent', self.useragent),
            ('Authorization', auth_string),
        ]

    def _request(self, url):
        """
        Requests the page as gzip and uncompresses it

        Returns a stream object

        """
        try:
            request = urllib.request.Request(url)
            request.add_header('Accept-Encoding', 'gzip')
            response = self.opener.open(request, timeout = 10)
        except urllib.request.HTTPError as e:
            if e.code == 401:
                raise utils.APIError(
                        "Unauthorized. Please check if your username and password are correct."
                        "\n\nPlease note that you might also be getting this error if you have "
                        "non-alphanumeric characters in your password due to an upstream "
                        "MAL bug (#138).")
            else:
                raise utils.APIError("HTTP error %d: %s" % (e.code, e.reason))
        except urllib.request.URLError as e:
            raise utils.APIError("Connection error: %s" % e)

        if response.info().get('content-encoding') == 'gzip':
            ret = gzip.decompress(response.read())
        else:
            # If the content is not gzipped return it as-is
            ret = response.read()
        if isinstance(ret, bytes):
            return ret.decode('utf-8')
        return ret

    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        if self.logged_in:
            return True     # Already logged in

        self.msg.info(self.name, 'Logging in...')

        response = self._request(self.url + "account/verify_credentials.xml")
        root = self._parse_xml(response)
        (userid, username) = self._parse_credentials(root)
        self.username = username

        self._set_userconfig('userid', userid)
        self._set_userconfig('username', username)
        self._emit_signal('userconfig_changed')

        self.logged_in = True
        return True

    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        try:
            # Get an XML list from MyAnimeList API
            data = self._request("https://myanimelist.net/malappinfo.php?u="+self.username+"&status=all&type="+self.mediatype)

            # Parse the XML data and load it into a dictionary
            # using the proper function (anime or manga)
            root = self._parse_xml(data)

            if self.mediatype == 'anime':
                self.msg.info(self.name, 'Parsing anime list...')
                return self._parse_anime(root)
            elif self.mediatype == 'manga':
                self.msg.info(self.name, 'Parsing manga list...')
                return self._parse_manga(root)
            else:
                raise utils.APIFatal('Attempted to parse unsupported media type.')
        except urllib.request.HTTPError as e:
            raise utils.APIError("Error getting list.")
        except IOError as e:
            raise utils.APIError("Error reading list: %s" % e)

    def add_show(self, item):
        """Adds a new show in the server"""
        self.check_credentials()
        self.msg.info(self.name, "Adding show %s..." % item['title'])

        xml = self._build_xml(item)

        # Send the XML as POST data to the MyAnimeList API
        values = {'data': xml}
        data = urllib.parse.urlencode(values)
        try:
            self.opener.open(self.url + self.mediatype + "list/add/" + str(item['id']) + ".xml", data.encode('utf-8'))
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error adding: ' + str(e.code))

    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])

        xml = self._build_xml(item)

        # Send the XML as POST data to the MyAnimeList API
        values = {'data': xml}
        data = urllib.parse.urlencode(values)
        try:
            self.opener.open(self.url + self.mediatype + "list/update/" + str(item['id']) + ".xml", data.encode('utf-8'))
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error updating: ' + str(e.code))

    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])

        try:
            self.opener.open(self.url + self.mediatype + "list/delete/" + str(item['id']) + ".xml")
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error deleting: ' + str(e.code))

    def search(self, criteria, method):
        """Searches MyAnimeList database for the queried show"""
        self.msg.info(self.name, "Searching for %s..." % criteria)

        # Send the urlencoded query to the search API
        query = urllib.parse.urlencode({'q': criteria})
        data = self._request(self.url + self.mediatype + "/search.xml?" + query)

        # Load the results into XML
        try:
            root = self._parse_xml(data)
        except ET.ParseError as e:
            if e.code == 3:
                # Empty document; no results
                return []
            else:
                raise utils.APIError("Parser error: %r" % e)
        except IOError:
            raise utils.APIError("IO error: %r" % e)

        # Use the correct tag name for episodes
        if self.mediatype == 'manga':
            episodes_str = 'chapters'
        else:
            episodes_str = 'episodes'

        # Since the MAL API returns the status as a string, and
        # we handle statuses as integers, we need to convert them
        if self.mediatype == 'anime':
            status_translate = {'Currently Airing': utils.STATUS_AIRING,
                    'Finished Airing': utils.STATUS_FINISHED,
                    'Not yet aired': utils.STATUS_NOTYET}
            type_translate = {'TV': utils.TYPE_TV,
                              'Movie': utils.TYPE_MOVIE,
                              'OVA': utils.TYPE_OVA,
                              'Special': utils.TYPE_SP}
        elif self.mediatype == 'manga':
            status_translate = {'Publishing': utils.STATUS_AIRING,
                    'Finished': utils.STATUS_AIRING}

        entries = list()
        for child in root.iter('entry'):
            show = utils.show()
            showid = int(child.find('id').text)
            show.update({
                'id':           showid,
                'title':        child.find('title').text,
                'type':         type_translate.get(child.find('type').text, utils.TYPE_OTHER),
                'status':       status_translate.get(child.find('status').text, utils.STATUS_OTHER),
                'total':        int(child.find(episodes_str).text),
                'image':        child.find('image').text,
                'url':          "https://myanimelist.net/anime/%d" % showid,
                'start_date':   self._str2date( child.find('start_date').text ),
                'end_date':     self._str2date( child.find('end_date').text ),
                'extra': [
                    ('English',  child.find('english').text),
                    ('Synonyms', child.find('synonyms').text),
                    ('Synopsis', self._translate_synopsis(child.find('synopsis').text)),
                    (episodes_str.title(), child.find(episodes_str).text),
                    ('Type',     child.find('type').text),
                    ('Score',    child.find('score').text),
                    ('Status',   child.find('status').text),
                    ('Start date', child.find('start_date').text),
                    ('End date', child.find('end_date').text),
                    ]
            })
            entries.append(show)

        self._emit_signal('show_info_changed', entries)
        return entries

    def _translate_synopsis(self, string):
        if string is None:
            return None
        else:
            return string.replace('<br />', '')

    def request_info(self, itemlist):
        resultdict = dict()
        for item in itemlist:
            # Search for it only if it hasn't been found earlier
            if item['id'] not in resultdict:
                infos = self.search(item['title'])
                for info in infos:
                    showid = info['id']
                    resultdict[showid] = info

        itemids = [ show['id'] for show in itemlist ]

        try:
            reslist = [ resultdict[itemid] for itemid in itemids ]
        except KeyError:
            raise utils.APIError('There was a problem getting the show details.')

        return reslist

    def _parse_credentials(self, root):
        if root is not None:
            userid = int(root.find('id').text)
            username = root.find('username').text
            return (userid, username)

    def _parse_anime(self, root):
        """Converts an XML anime list to a dictionary"""
        showlist = dict()
        for child in root.iter('anime'):
            show_id = int(child.find('series_animedb_id').text)
            if child.find('series_synonyms').text:
                aliases = child.find('series_synonyms').text.lstrip('; ').split('; ')
            else:
                aliases = []

            show = utils.show()
            show.update({
                'id':           show_id,
                'title':        child.find('series_title').text,
                'aliases':      aliases,
                'my_progress':  int(child.find('my_watched_episodes').text),
                'my_status':    int(child.find('my_status').text),
                'my_score':     int(child.find('my_score').text),
                'my_start_date':  self._str2date( child.find('my_start_date').text ),
                'my_finish_date': self._str2date( child.find('my_finish_date').text ),
                'my_tags':         child.find('my_tags').text,
                'total':     int(child.find('series_episodes').text),
                'status':       int(child.find('series_status').text),
                'start_date':   self._str2date( child.find('series_start').text ),
                'end_date':     self._str2date( child.find('series_end').text ),
                'image':        child.find('series_image').text,
                'url':          "https://myanimelist.net/anime/%d" % show_id,
            })
            showlist[show_id] = show
        return showlist

    def _parse_manga(self, root):
        """Converts an XML manga list to a dictionary"""
        mangalist = dict()
        for child in root.iter('manga'):
            manga_id = int(child.find('series_mangadb_id').text)
            if child.find('series_synonyms').text:
                aliases = child.find('series_synonyms').text.lstrip('; ').split('; ')
            else:
                aliases = []

            show = utils.show()
            show.update({
                'id':           manga_id,
                'title':        child.find('series_title').text,
                'aliases':      aliases,
                'my_progress':  int(child.find('my_read_chapters').text),
                'my_status':    int(child.find('my_status').text),
                'my_score':     int(child.find('my_score').text),
                'my_start_date':  self._str2date( child.find('my_start_date').text ),
                'my_finish_date': self._str2date( child.find('my_finish_date').text ),
                'total':     int(child.find('series_chapters').text),
                'status':       int(child.find('series_status').text),
                'start_date':   self._str2date( child.find('series_start').text ),
                'end_date':     self._str2date( child.find('series_end').text ),
                'image':        child.find('series_image').text,
                'url':          "https://myanimelist.net/manga/%d" % manga_id,
            })
            mangalist[manga_id] = show
        return mangalist

    def _build_xml(self, item):
        """
        Creates an "anime|manga data" XML to be used in the
        add, update and delete methods.

        More information:
          https://myanimelist.net/modules.php?go=api#animevalues
          https://myanimelist.net/modules.php?go=api#mangavalues

        """

        # Start building XML
        root = ET.Element("entry")

        # Use the correct name depending on mediatype
        if self.mediatype == 'anime':
            progressname = 'episode'
        else:
            progressname = 'chapter'

        # Update necessary keys
        if 'my_progress' in item:
            episode = ET.SubElement(root, progressname)
            episode.text = str(item['my_progress'])
        if 'my_status' in item:
            status = ET.SubElement(root, "status")
            status.text = str(item['my_status'])
        if 'my_score' in item:
            score = ET.SubElement(root, "score")
            score.text = str(item['my_score'])
        if 'my_start_date' in item:
            start_date = ET.SubElement(root, "date_start")
            start_date.text = self._date2str(item['my_start_date'])
        if 'my_finish_date' in item:
            finish_date = ET.SubElement(root, "date_finish")
            finish_date.text = self._date2str(item['my_finish_date'])
        if 'my_tags' in item:
            tags = ET.SubElement(root, "tags")
            tags.text = str(item['my_tags'])

        return ET.tostring(root)

    def _date2str(self, date):
        if date:
            return date.strftime("%m%d%Y")
        else:
            return '0000-00-00'

    def _str2date(self, string):
        if string != '0000-00-00':
            try:
                return datetime.datetime.strptime(string, "%Y-%m-%d")
            except ValueError:
                return None # Ignore date if it's invalid
        else:
            return None

    def _parse_xml(self, data):
        # For some reason MAL returns an XML file with HTML exclusive
        # entities like &aacute;, so we have to create a custom XMLParser
        # to convert these entities correctly.

        ENTITIES = {
            "nbsp":     u'\u00A0',
            "iexcl":    u'\u00A1',
            "cent":     u'\u00A2',
            "pound":    u'\u00A3',
            "curren":   u'\u00A4',
            "yen":      u'\u00A5',
            "brvbar":   u'\u00A6',
            "sect":     u'\u00A7',
            "uml":      u'\u00A8',
            "copy":     u'\u00A9',
            "ordf":     u'\u00AA',
            "laquo":    u'\u00AB',
            "not":      u'\u00AC',
            "shy":      u'\u00AD',
            "reg":      u'\u00AE',
            "macr":     u'\u00AF',
            "deg":      u'\u00B0',
            "plusmn":   u'\u00B1',
            "sup2":     u'\u00B2',
            "sup3":     u'\u00B3',
            "acute":    u'\u00B4',
            "micro":    u'\u00B5',
            "para":     u'\u00B6',
            "middot":   u'\u00B7',
            "cedil":    u'\u00B8',
            "sup1":     u'\u00B9',
            "ordm":     u'\u00BA',
            "raquo":    u'\u00BB',
            "frac14":   u'\u00BC',
            "frac12":   u'\u00BD',
            "frac34":   u'\u00BE',
            "iquest":   u'\u00BF',
            "Agrave":   u'\u00C0',
            "Aacute":   u'\u00C1',
            "Acirc":    u'\u00C2',
            "Atilde":   u'\u00C3',
            "Auml":     u'\u00C4',
            "Aring":    u'\u00C5',
            "AElig":    u'\u00C6',
            "Ccedil":   u'\u00C7',
            "Egrave":   u'\u00C8',
            "Eacute":   u'\u00C9',
            "Ecirc":    u'\u00CA',
            "Euml":     u'\u00CB',
            "Igrave":   u'\u00CC',
            "Iacute":   u'\u00CD',
            "Icirc":    u'\u00CE',
            "Iuml":     u'\u00CF',
            "ETH":      u'\u00D0',
            "Ntilde":   u'\u00D1',
            "Ograve":   u'\u00D2',
            "Oacute":   u'\u00D3',
            "Ocirc":    u'\u00D4',
            "Otilde":   u'\u00D5',
            "Ouml":     u'\u00D6',
            "times":    u'\u00D7',
            "Oslash":   u'\u00D8',
            "Ugrave":   u'\u00D9',
            "Uacute":   u'\u00DA',
            "Ucirc":    u'\u00DB',
            "Uuml":     u'\u00DC',
            "Yacute":   u'\u00DD',
            "THORN":    u'\u00DE',
            "szlig":    u'\u00DF',
            "agrave":   u'\u00E0',
            "aacute":   u'\u00E1',
            "acirc":    u'\u00E2',
            "atilde":   u'\u00E3',
            "auml":     u'\u00E4',
            "aring":    u'\u00E5',
            "aelig":    u'\u00E6',
            "ccedil":   u'\u00E7',
            "egrave":   u'\u00E8',
            "eacute":   u'\u00E9',
            "ecirc":    u'\u00EA',
            "euml":     u'\u00EB',
            "igrave":   u'\u00EC',
            "iacute":   u'\u00ED',
            "icirc":    u'\u00EE',
            "iuml":     u'\u00EF',
            "eth":      u'\u00F0',
            "ntilde":   u'\u00F1',
            "ograve":   u'\u00F2',
            "oacute":   u'\u00F3',
            "ocirc":    u'\u00F4',
            "otilde":   u'\u00F5',
            "ouml":     u'\u00F6',
            "divide":   u'\u00F7',
            "oslash":   u'\u00F8',
            "ugrave":   u'\u00F9',
            "uacute":   u'\u00FA',
            "ucirc":    u'\u00FB',
            "uuml":     u'\u00FC',
            "yacute":   u'\u00FD',
            "thorn":    u'\u00FE',
            "yuml":     u'\u00FF',
            "fnof":     u'\u0192',
            "Alpha":    u'\u0391',
            "Beta":     u'\u0392',
            "Gamma":    u'\u0393',
            "Delta":    u'\u0394',
            "Epsilon":  u'\u0395',
            "Zeta":     u'\u0396',
            "Eta":      u'\u0397',
            "Theta":    u'\u0398',
            "Iota":     u'\u0399',
            "Kappa":    u'\u039A',
            "Lambda":   u'\u039B',
            "Mu":       u'\u039C',
            "Nu":       u'\u039D',
            "Xi":       u'\u039E',
            "Omicron":  u'\u039F',
            "Pi":       u'\u03A0',
            "Rho":      u'\u03A1',
            "Sigma":    u'\u03A3',
            "Tau":      u'\u03A4',
            "Upsilon":  u'\u03A5',
            "Phi":      u'\u03A6',
            "Chi":      u'\u03A7',
            "Psi":      u'\u03A8',
            "Omega":    u'\u03A9',
            "alpha":    u'\u03B1',
            "beta":     u'\u03B2',
            "gamma":    u'\u03B3',
            "delta":    u'\u03B4',
            "epsilon":  u'\u03B5',
            "zeta":     u'\u03B6',
            "eta":      u'\u03B7',
            "theta":    u'\u03B8',
            "iota":     u'\u03B9',
            "kappa":    u'\u03BA',
            "lambda":   u'\u03BB',
            "mu":       u'\u03BC',
            "nu":       u'\u03BD',
            "xi":       u'\u03BE',
            "omicron":  u'\u03BF',
            "pi":       u'\u03C0',
            "rho":      u'\u03C1',
            "sigmaf":   u'\u03C2',
            "sigma":    u'\u03C3',
            "tau":      u'\u03C4',
            "upsilon":  u'\u03C5',
            "phi":      u'\u03C6',
            "chi":      u'\u03C7',
            "psi":      u'\u03C8',
            "omega":    u'\u03C9',
            "thetasym": u'\u03D1',
            "upsih":    u'\u03D2',
            "piv":      u'\u03D6',
            "bull":     u'\u2022',
            "hellip":   u'\u2026',
            "prime":    u'\u2032',
            "Prime":    u'\u2033',
            "oline":    u'\u203E',
            "frasl":    u'\u2044',
            "weierp":   u'\u2118',
            "image":    u'\u2111',
            "real":     u'\u211C',
            "trade":    u'\u2122',
            "alefsym":  u'\u2135',
            "larr":     u'\u2190',
            "uarr":     u'\u2191',
            "rarr":     u'\u2192',
            "darr":     u'\u2193',
            "harr":     u'\u2194',
            "crarr":    u'\u21B5',
            "lArr":     u'\u21D0',
            "uArr":     u'\u21D1',
            "rArr":     u'\u21D2',
            "dArr":     u'\u21D3',
            "hArr":     u'\u21D4',
            "forall":   u'\u2200',
            "part":     u'\u2202',
            "exist":    u'\u2203',
            "empty":    u'\u2205',
            "nabla":    u'\u2207',
            "isin":     u'\u2208',
            "notin":    u'\u2209',
            "ni":       u'\u220B',
            "prod":     u'\u220F',
            "sum":      u'\u2211',
            "minus":    u'\u2212',
            "lowast":   u'\u2217',
            "radic":    u'\u221A',
            "prop":     u'\u221D',
            "infin":    u'\u221E',
            "ang":      u'\u2220',
            "and":      u'\u2227',
            "or":       u'\u2228',
            "cap":      u'\u2229',
            "cup":      u'\u222A',
            "int":      u'\u222B',
            "there4":   u'\u2234',
            "sim":      u'\u223C',
            "cong":     u'\u2245',
            "asymp":    u'\u2248',
            "ne":       u'\u2260',
            "equiv":    u'\u2261',
            "le":       u'\u2264',
            "ge":       u'\u2265',
            "sub":      u'\u2282',
            "sup":      u'\u2283',
            "nsub":     u'\u2284',
            "sube":     u'\u2286',
            "supe":     u'\u2287',
            "oplus":    u'\u2295',
            "otimes":   u'\u2297',
            "perp":     u'\u22A5',
            "sdot":     u'\u22C5',
            "lceil":    u'\u2308',
            "rceil":    u'\u2309',
            "lfloor":   u'\u230A',
            "rfloor":   u'\u230B',
            "lang":     u'\u2329',
            "rang":     u'\u232A',
            "loz":      u'\u25CA',
            "spades":   u'\u2660',
            "clubs":    u'\u2663',
            "hearts":   u'\u2665',
            "diams":    u'\u2666',
            "quot":     u'\"'    ,
            "amp":      u'&'     ,
            "lt":       u'<'     ,
            "gt":       u'>'     ,
            "OElig":    u'\u0152',
            "oelig":    u'\u0153',
            "Scaron":   u'\u0160',
            "scaron":   u'\u0161',
            "Yuml":     u'\u0178',
            "circ":     u'\u02C6',
            "tilde":    u'\u02DC',
            "ensp":     u'\u2002',
            "emsp":     u'\u2003',
            "thinsp":   u'\u2009',
            "zwnj":     u'\u200C',
            "zwj":      u'\u200D',
            "lrm":      u'\u200E',
            "rlm":      u'\u200F',
            "ndash":    u'\u2013',
            "mdash":    u'\u2014',
            "lsquo":    u'\u2018',
            "rsquo":    u'\u2019',
            "sbquo":    u'\u201A',
            "ldquo":    u'\u201C',
            "rdquo":    u'\u201D',
            "bdquo":    u'\u201E',
            "dagger":   u'\u2020',
            "Dagger":   u'\u2021',
            "permil":   u'\u2030',
            "lsaquo":   u'\u2039',
            "rsaquo":   u'\u203A',
            "euro":     u'\u20AC',
        }

        # http://stackoverflow.com/a/35591479/2016221
        magic = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
            "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd" [\n'''
        magic += ''.join("<!ENTITY %s '&#%d;'>\n" % (key, ord(value)) for key, value in ENTITIES.items())
        magic += '\n]>'

        # strip xml declaration since we're concatenating something before it
        data = re.sub('<\?.*?\?>', '', data)

        return ET.fromstring(magic + data)
