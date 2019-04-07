from trackma import utils
from trackma.extras import AnimeInfoExtractor

import pickle
import urllib.request
import xml.etree.ElementTree as ET
import gzip
from io import StringIO

STATUS_NEXT_EPISODE = 1
STATUS_NOT_NEXT_EPISODE = 2
STATUS_WATCHED = 3
STATUS_NOT_FOUND = 4
STATUS_NOT_RECOGNIZED = 5

class Torrents(object):
    torrents = {}
    name = 'Torrents'

    # Hardcoded for now
    #FEED_URL = "http://www.nyaa.se/?page=rss&cats=1_37"
    FEED_URL = "http://tokyotosho.se/rss.php?filter=1&zwnj=0"

    def __init__(self, messenger, animelist, config):
        self.animelist = animelist
        self.msg = messenger
        utils.make_dir(utils.to_data_path())
        self.filename = utils.to_data_path('torrents.dict')
        self._load()

    def _load(self):
        if utils.file_exists(self.filename):
            with open(self.filename, 'rb') as f:
                self.torrents = cpickle.load(f)

    def _save(self):
        with open(self.filename, 'wb') as f:
            cpickle.dump(self.torrents, f)

    def _download_feed(self, url):
        req = urllib.request.Request(url)
        req.add_header('Accept-Encoding', 'gzip')
        response = urllib.request.urlopen(req)

        if response.info().get('content-encoding') == 'gzip':
            stream = StringIO(response.read())
            result = gzip.GzipFile(fileobj=stream)
        else:
            result = response

        return ET.parse(result).getroot()
        #return ET.parse(result)

    def _parse_feed(self, dom):
        channel = dom.find('channel')
        for node in channel.findall('item'):
            item = {}
            for child in node:
                if child.tag == 'title':
                    item['title'] = child.text
                elif child.tag == 'link':
                    item['link'] = child.text
                elif child.tag == 'description':
                    item['description'] = child.text

            yield item

    def get_torrents(self):
        torrents_keys = self.torrents.keys()

        self.msg.info(self.name, "Downloading torrent feed...")
        dom = self._download_feed(self.FEED_URL)
        self.msg.info(self.name, "Parsing torrents...")
        items = self._parse_feed(dom)
        for item in items:
            if item['title'] in torrents_keys:
                continue # Already cached

            torrent = {
                       'filename': item['title'],
                       'url': item['link'],
                       'show_id': None,
                       'show_title': None,
                       'show_episode': None,
                       'show_group': None,
                       'status': STATUS_NOT_FOUND,
                      }

            highest_ratio = (None, 0)
            aie = extras.AnimeInfoExtractor.AnimeInfoExtractor(item['title'])
            (item_title, item_episode, item_group) = (aie.getName(), aie.getEpisode(), aie.subberTag)

            torrent['show_title'] = item_title
            torrent['show_episode'] = item_episode
            torrent['show_group'] = item_group

            if not item_title:
                torrent['status'] = STATUS_NOT_RECOGNIZED
                continue

            show = utils.guess_show(item_title, self.animelist)

            if show:
                torrent['show_id'] = show['id']
                #torrent['show_title'] = show['title']

                if item_episode == (show['my_progress'] + 1):
                    # Show found!
                    torrent['status'] = STATUS_NEXT_EPISODE
                elif item_episode > (show['my_progress'] + 1):
                    torrent['status'] = STATUS_NOT_NEXT_EPISODE
                else:
                    # The show was found but this episode was already watched
                    torrent['status'] = STATUS_WATCHED
            else:
                # This show isn't in the list
                pass

            # Add to the list
            self.torrents[item['title']] = torrent

        self._save()
        return self.torrents

    def get_sorted_torrents(self):
        from operator import itemgetter
        d = self.get_torrents().values()
        return sorted(d, key=itemgetter('status'))

