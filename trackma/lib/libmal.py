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

from trackma.lib.lib import lib
import trackma.utils as utils

import urllib, urllib2
import datetime
import base64
import gzip
import xml.etree.ElementTree as ET
from cStringIO import StringIO

class libmal(lib):
    """
    API class to communicate with MyAnimeList
    Should inherit a base library interface.

    Website: http://www.myanimelist.net
    API documentation: http://myanimelist.net/modules.php?go=api
    Designed by: Garrett Gyssler (http://myanimelist.net/profile/Xinil)

    """
    name = 'libmal'

    username = '' # TODO Must be filled by check_credentials
    logged_in = False
    opener = None

    api_info =  { 'name': 'MyAnimeList', 'shortname': 'mal', 'version': 'v0.3', 'merge': False }

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
    url = 'http://myanimelist.net/api/'
    useragent = 'api-team-f894427cc1c571f79da49605ef8b112f'

    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        # Since MyAnimeList uses a cookie we just create a HTTP Auth handler
        # together with the urllib2 opener.
        super(libmal, self).__init__(messenger, account, userconfig)

        auth_string = 'Basic ' + base64.encodestring('%s:%s' % (account['username'], account['password'])).replace('\n', '')

        self.username = self._get_userconfig('username')
        self.opener = urllib2.build_opener()
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
            request = urllib2.Request(url)
            request.add_header('Accept-Encoding', 'gzip')
            response = self.opener.open(request, timeout = 10)
        except urllib2.HTTPError, e:
            if e.code == 401:
                raise utils.APIError(
                        "Unauthorized. Please check if your username and password are correct."
                        "\n\nPlease note that you might also be getting this error if you have "
                        "non-alphanumeric characters in your password due to an upstream "
                        "MAL bug (#138).")
            else:
                raise utils.APIError("HTTP error %d: %s" % (e.code, e.reason))
        except urllib2.URLError, e:
            raise utils.APIError("Connection error: %s" % e)

        if response.info().get('content-encoding') == 'gzip':
            compressed_stream = StringIO(response.read())
            return gzip.GzipFile(fileobj=compressed_stream)
        else:
            # If the content is not gzipped return it as-is
            return response

    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        if self.logged_in:
            return True     # Already logged in

        self.msg.info(self.name, 'Logging in...')

        response = self._request(self.url + "account/verify_credentials.xml")
        root = ET.ElementTree().parse(response, parser=self._make_parser())
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
            data = self._request("http://myanimelist.net/malappinfo.php?u="+self.username+"&status=all&type="+self.mediatype)

            # Parse the XML data and load it into a dictionary
            # using the proper function (anime or manga)
            root = ET.ElementTree().parse(data, parser=self._make_parser())

            if self.mediatype == 'anime':
                self.msg.info(self.name, 'Parsing anime list...')
                return self._parse_anime(root)
            elif self.mediatype == 'manga':
                self.msg.info(self.name, 'Parsing manga list...')
                return self._parse_manga(root)
            else:
                raise utils.APIFatal('Attempted to parse unsupported media type.')
        except urllib2.HTTPError, e:
            raise utils.APIError("Error getting list.")
        except IOError, e:
            raise utils.APIError("Error reading list: %s" % e.message)

    def add_show(self, item):
        """Adds a new show in the server"""
        self.check_credentials()
        self.msg.info(self.name, "Adding show %s..." % item['title'])

        xml = self._build_xml(item)

        # Send the XML as POST data to the MyAnimeList API
        values = {'data': xml}
        data = self._urlencode(values)
        try:
            self.opener.open(self.url + self.mediatype + "list/add/" + str(item['id']) + ".xml", data)
        except urllib2.HTTPError, e:
            raise utils.APIError('Error adding: ' + str(e.code))

    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])

        xml = self._build_xml(item)

        # Send the XML as POST data to the MyAnimeList API
        values = {'data': xml}
        data = self._urlencode(values)
        try:
            self.opener.open(self.url + self.mediatype + "list/update/" + str(item['id']) + ".xml", data)
        except urllib2.HTTPError, e:
            raise utils.APIError('Error updating: ' + str(e.code))

    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])

        try:
            self.opener.open(self.url + self.mediatype + "list/delete/" + str(item['id']) + ".xml")
        except urllib2.HTTPError, e:
            raise utils.APIError('Error deleting: ' + str(e.code))

    def search(self, criteria):
        """Searches MyAnimeList database for the queried show"""
        self.msg.info(self.name, "Searching for %s..." % criteria)

        # Send the urlencoded query to the search API
        query = self._urlencode({'q': criteria})
        data = self._request(self.url + self.mediatype + "/search.xml?" + query)

        # Load the results into XML
        try:
            root = ET.ElementTree().parse(data, parser=self._make_parser())
        except ET.ParseError, e:
            if e.code == 3:
                # Empty document; no results
                return []
            else:
                raise utils.APIError("Parser error: %s" % repr(e.message))
        except IOError:
            raise utils.APIError("IO error: %s" % repr(e.message))

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
                'type':         child.find('type').text,
                'status':       status_translate[child.find('status').text], # TODO : This should return an int!
                'total':        int(child.find(episodes_str).text),
                'image':        child.find('image').text,
                'url':          "http://myanimelist.net/anime/%d" % showid,
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
                'url':          "http://myanimelist.net/anime/%d" % show_id,
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
                'url':          "http://myanimelist.net/manga/%d" % manga_id,
            })
            mangalist[manga_id] = show
        return mangalist

    def _build_xml(self, item):
        """
        Creates an "anime|manga data" XML to be used in the
        add, update and delete methods.

        More information:
          http://myanimelist.net/modules.php?go=api#animevalues
          http://myanimelist.net/modules.php?go=api#mangavalues

        """

        # Start building XML
        root = ET.Element("entry")

        # Use the correct name depending on mediatype
        if self.mediatype == 'anime':
            progressname = 'episode'
        else:
            progressname = 'chapter'

        # Update necessary keys
        if 'my_progress' in item.keys():
            episode = ET.SubElement(root, progressname)
            episode.text = str(item['my_progress'])
        if 'my_status' in item.keys():
            status = ET.SubElement(root, "status")
            status.text = str(item['my_status'])
        if 'my_score' in item.keys():
            score = ET.SubElement(root, "score")
            score.text = str(item['my_score'])
        if 'my_start_date' in item.keys():
            start_date = ET.SubElement(root, "date_start")
            start_date.text = self._date2str(item['my_start_date'])
        if 'my_finish_date' in item.keys():
            finish_date = ET.SubElement(root, "date_finish")
            finish_date.text = self._date2str(item['my_finish_date'])
        if 'my_tags' in item.keys():
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

    def _urlencode(self, in_dict):
        """Helper function to urlencode dicts in unicode. urllib doesn't like them."""
        out_dict = {}
        for k, v in in_dict.iteritems():
            out_dict[k] = v
            if isinstance(v, unicode):
                out_dict[k] = v.encode('utf8')
            elif isinstance(v, str):
                out_dict[k] = v.decode('utf8')
        return urllib.urlencode(out_dict)

    def _make_parser(self):
        # For some reason MAL returns an XML file with HTML exclusive
        # entities like &aacute;, so we have to create a custom XMLParser
        # to convert these entities correctly.
        parser = ET.XMLParser()
        parser.parser.UseForeignDTD(True)

        entities = dict()
        entities["nbsp"] =     u'\u00A0'
        entities["iexcl"] =    u'\u00A1'
        entities["cent"] =     u'\u00A2'
        entities["pound"] =    u'\u00A3'
        entities["curren"] =   u'\u00A4'
        entities["yen"] =      u'\u00A5'
        entities["brvbar"] =   u'\u00A6'
        entities["sect"] =     u'\u00A7'
        entities["uml"] =      u'\u00A8'
        entities["copy"] =     u'\u00A9'
        entities["ordf"] =     u'\u00AA'
        entities["laquo"] =    u'\u00AB'
        entities["not"] =      u'\u00AC'
        entities["shy"] =      u'\u00AD'
        entities["reg"] =      u'\u00AE'
        entities["macr"] =     u'\u00AF'
        entities["deg"] =      u'\u00B0'
        entities["plusmn"] =   u'\u00B1'
        entities["sup2"] =     u'\u00B2'
        entities["sup3"] =     u'\u00B3'
        entities["acute"] =    u'\u00B4'
        entities["micro"] =    u'\u00B5'
        entities["para"] =     u'\u00B6'
        entities["middot"] =   u'\u00B7'
        entities["cedil"] =    u'\u00B8'
        entities["sup1"] =     u'\u00B9'
        entities["ordm"] =     u'\u00BA'
        entities["raquo"] =    u'\u00BB'
        entities["frac14"] =   u'\u00BC'
        entities["frac12"] =   u'\u00BD'
        entities["frac34"] =   u'\u00BE'
        entities["iquest"] =   u'\u00BF'
        entities["Agrave"] =   u'\u00C0'
        entities["Aacute"] =   u'\u00C1'
        entities["Acirc"] =    u'\u00C2'
        entities["Atilde"] =   u'\u00C3'
        entities["Auml"] =     u'\u00C4'
        entities["Aring"] =    u'\u00C5'
        entities["AElig"] =    u'\u00C6'
        entities["Ccedil"] =   u'\u00C7'
        entities["Egrave"] =   u'\u00C8'
        entities["Eacute"] =   u'\u00C9'
        entities["Ecirc"] =    u'\u00CA'
        entities["Euml"] =     u'\u00CB'
        entities["Igrave"] =   u'\u00CC'
        entities["Iacute"] =   u'\u00CD'
        entities["Icirc"] =    u'\u00CE'
        entities["Iuml"] =     u'\u00CF'
        entities["ETH"] =      u'\u00D0'
        entities["Ntilde"] =   u'\u00D1'
        entities["Ograve"] =   u'\u00D2'
        entities["Oacute"] =   u'\u00D3'
        entities["Ocirc"] =    u'\u00D4'
        entities["Otilde"] =   u'\u00D5'
        entities["Ouml"] =     u'\u00D6'
        entities["times"] =    u'\u00D7'
        entities["Oslash"] =   u'\u00D8'
        entities["Ugrave"] =   u'\u00D9'
        entities["Uacute"] =   u'\u00DA'
        entities["Ucirc"] =    u'\u00DB'
        entities["Uuml"] =     u'\u00DC'
        entities["Yacute"] =   u'\u00DD'
        entities["THORN"] =    u'\u00DE'
        entities["szlig"] =    u'\u00DF'
        entities["agrave"] =   u'\u00E0'
        entities["aacute"] =   u'\u00E1'
        entities["acirc"] =    u'\u00E2'
        entities["atilde"] =   u'\u00E3'
        entities["auml"] =     u'\u00E4'
        entities["aring"] =    u'\u00E5'
        entities["aelig"] =    u'\u00E6'
        entities["ccedil"] =   u'\u00E7'
        entities["egrave"] =   u'\u00E8'
        entities["eacute"] =   u'\u00E9'
        entities["ecirc"] =    u'\u00EA'
        entities["euml"] =     u'\u00EB'
        entities["igrave"] =   u'\u00EC'
        entities["iacute"] =   u'\u00ED'
        entities["icirc"] =    u'\u00EE'
        entities["iuml"] =     u'\u00EF'
        entities["eth"] =      u'\u00F0'
        entities["ntilde"] =   u'\u00F1'
        entities["ograve"] =   u'\u00F2'
        entities["oacute"] =   u'\u00F3'
        entities["ocirc"] =    u'\u00F4'
        entities["otilde"] =   u'\u00F5'
        entities["ouml"] =     u'\u00F6'
        entities["divide"] =   u'\u00F7'
        entities["oslash"] =   u'\u00F8'
        entities["ugrave"] =   u'\u00F9'
        entities["uacute"] =   u'\u00FA'
        entities["ucirc"] =    u'\u00FB'
        entities["uuml"] =     u'\u00FC'
        entities["yacute"] =   u'\u00FD'
        entities["thorn"] =    u'\u00FE'
        entities["yuml"] =     u'\u00FF'
        entities["fnof"] =     u'\u0192'
        entities["Alpha"] =    u'\u0391'
        entities["Beta"] =     u'\u0392'
        entities["Gamma"] =    u'\u0393'
        entities["Delta"] =    u'\u0394'
        entities["Epsilon"] =  u'\u0395'
        entities["Zeta"] =     u'\u0396'
        entities["Eta"] =      u'\u0397'
        entities["Theta"] =    u'\u0398'
        entities["Iota"] =     u'\u0399'
        entities["Kappa"] =    u'\u039A'
        entities["Lambda"] =   u'\u039B'
        entities["Mu"] =       u'\u039C'
        entities["Nu"] =       u'\u039D'
        entities["Xi"] =       u'\u039E'
        entities["Omicron"] =  u'\u039F'
        entities["Pi"] =       u'\u03A0'
        entities["Rho"] =      u'\u03A1'
        entities["Sigma"] =    u'\u03A3'
        entities["Tau"] =      u'\u03A4'
        entities["Upsilon"] =  u'\u03A5'
        entities["Phi"] =      u'\u03A6'
        entities["Chi"] =      u'\u03A7'
        entities["Psi"] =      u'\u03A8'
        entities["Omega"] =    u'\u03A9'
        entities["alpha"] =    u'\u03B1'
        entities["beta"] =     u'\u03B2'
        entities["gamma"] =    u'\u03B3'
        entities["delta"] =    u'\u03B4'
        entities["epsilon"] =  u'\u03B5'
        entities["zeta"] =     u'\u03B6'
        entities["eta"] =      u'\u03B7'
        entities["theta"] =    u'\u03B8'
        entities["iota"] =     u'\u03B9'
        entities["kappa"] =    u'\u03BA'
        entities["lambda"] =   u'\u03BB'
        entities["mu"] =       u'\u03BC'
        entities["nu"] =       u'\u03BD'
        entities["xi"] =       u'\u03BE'
        entities["omicron"] =  u'\u03BF'
        entities["pi"] =       u'\u03C0'
        entities["rho"] =      u'\u03C1'
        entities["sigmaf"] =   u'\u03C2'
        entities["sigma"] =    u'\u03C3'
        entities["tau"] =      u'\u03C4'
        entities["upsilon"] =  u'\u03C5'
        entities["phi"] =      u'\u03C6'
        entities["chi"] =      u'\u03C7'
        entities["psi"] =      u'\u03C8'
        entities["omega"] =    u'\u03C9'
        entities["thetasym"] = u'\u03D1'
        entities["upsih"] =    u'\u03D2'
        entities["piv"] =      u'\u03D6'
        entities["bull"] =     u'\u2022'
        entities["hellip"] =   u'\u2026'
        entities["prime"] =    u'\u2032'
        entities["Prime"] =    u'\u2033'
        entities["oline"] =    u'\u203E'
        entities["frasl"] =    u'\u2044'
        entities["weierp"] =   u'\u2118'
        entities["image"] =    u'\u2111'
        entities["real"] =     u'\u211C'
        entities["trade"] =    u'\u2122'
        entities["alefsym"] =  u'\u2135'
        entities["larr"] =     u'\u2190'
        entities["uarr"] =     u'\u2191'
        entities["rarr"] =     u'\u2192'
        entities["darr"] =     u'\u2193'
        entities["harr"] =     u'\u2194'
        entities["crarr"] =    u'\u21B5'
        entities["lArr"] =     u'\u21D0'
        entities["uArr"] =     u'\u21D1'
        entities["rArr"] =     u'\u21D2'
        entities["dArr"] =     u'\u21D3'
        entities["hArr"] =     u'\u21D4'
        entities["forall"] =   u'\u2200'
        entities["part"] =     u'\u2202'
        entities["exist"] =    u'\u2203'
        entities["empty"] =    u'\u2205'
        entities["nabla"] =    u'\u2207'
        entities["isin"] =     u'\u2208'
        entities["notin"] =    u'\u2209'
        entities["ni"] =       u'\u220B'
        entities["prod"] =     u'\u220F'
        entities["sum"] =      u'\u2211'
        entities["minus"] =    u'\u2212'
        entities["lowast"] =   u'\u2217'
        entities["radic"] =    u'\u221A'
        entities["prop"] =     u'\u221D'
        entities["infin"] =    u'\u221E'
        entities["ang"] =      u'\u2220'
        entities["and"] =      u'\u2227'
        entities["or"] =       u'\u2228'
        entities["cap"] =      u'\u2229'
        entities["cup"] =      u'\u222A'
        entities["int"] =      u'\u222B'
        entities["there4"] =   u'\u2234'
        entities["sim"] =      u'\u223C'
        entities["cong"] =     u'\u2245'
        entities["asymp"] =    u'\u2248'
        entities["ne"] =       u'\u2260'
        entities["equiv"] =    u'\u2261'
        entities["le"] =       u'\u2264'
        entities["ge"] =       u'\u2265'
        entities["sub"] =      u'\u2282'
        entities["sup"] =      u'\u2283'
        entities["nsub"] =     u'\u2284'
        entities["sube"] =     u'\u2286'
        entities["supe"] =     u'\u2287'
        entities["oplus"] =    u'\u2295'
        entities["otimes"] =   u'\u2297'
        entities["perp"] =     u'\u22A5'
        entities["sdot"] =     u'\u22C5'
        entities["lceil"] =    u'\u2308'
        entities["rceil"] =    u'\u2309'
        entities["lfloor"] =   u'\u230A'
        entities["rfloor"] =   u'\u230B'
        entities["lang"] =     u'\u2329'
        entities["rang"] =     u'\u232A'
        entities["loz"] =      u'\u25CA'
        entities["spades"] =   u'\u2660'
        entities["clubs"] =    u'\u2663'
        entities["hearts"] =   u'\u2665'
        entities["diams"] =    u'\u2666'
        entities["quot"] =     u'\"'
        entities["amp"] =      u'&'
        entities["lt"] =       u'<'
        entities["gt"] =       u'>'
        entities["OElig"] =    u'\u0152'
        entities["oelig"] =    u'\u0153'
        entities["Scaron"] =   u'\u0160'
        entities["scaron"] =   u'\u0161'
        entities["Yuml"] =     u'\u0178'
        entities["circ"] =     u'\u02C6'
        entities["tilde"] =    u'\u02DC'
        entities["ensp"] =     u'\u2002'
        entities["emsp"] =     u'\u2003'
        entities["thinsp"] =   u'\u2009'
        entities["zwnj"] =     u'\u200C'
        entities["zwj"] =      u'\u200D'
        entities["lrm"] =      u'\u200E'
        entities["rlm"] =      u'\u200F'
        entities["ndash"] =    u'\u2013'
        entities["mdash"] =    u'\u2014'
        entities["lsquo"] =    u'\u2018'
        entities["rsquo"] =    u'\u2019'
        entities["sbquo"] =    u'\u201A'
        entities["ldquo"] =    u'\u201C'
        entities["rdquo"] =    u'\u201D'
        entities["bdquo"] =    u'\u201E'
        entities["dagger"] =   u'\u2020'
        entities["Dagger"] =   u'\u2021'
        entities["permil"] =   u'\u2030'
        entities["lsaquo"] =   u'\u2039'
        entities["rsaquo"] =   u'\u203A'
        entities["euro"] =     u'\u20AC'
        parser.entity.update(entities)

        return parser

