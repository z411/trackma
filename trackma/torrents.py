import utils
import extras.AnimeInfoExtractor

import cPickle
import urllib2
import xml.etree.ElementTree as ET
import gzip
from cStringIO import StringIO

class Torrents(object):
    STATUS_NEXT_EPISODE = 1
    STATUS_NOT_NEXT_EPISODE = 2
    STATUS_WATCHED = 3
    STATUS_NOT_FOUND = 4
    STATUS_NOT_RECOGNIZED = 5

    torrents = {}
    name = 'Torrents'

    # Hardcoded for now
    #FEED_URL = "http://www.nyaa.se/?page=rss&cats=1_37"
    FEED_URL = "http://tokyotosho.se/rss.php?filter=1&zwnj=0"

    def __init__(self, messenger, animelist, config):
        self.animelist = animelist
        utils.make_dir('')
        self.filename = utils.get_root_filename('torrents.dict')
        self._load()

    def _load(self):
        if utils.file_exists(self.filename):
            with open(self.filename, 'rb') as f:
                self.torrents = cPickle.load(f)

    def _save(self):
        with open(self.filename, 'wb') as f:
            cPickle.dump(self.torrents, f)

    def _download_feed(self, url):
        req = urllib2.Request(url)
        req.add_header('Accept-Encoding', 'gzip')
        response = urllib2.urlopen(req)

        if response.info().get('content-encoding') == 'gzip':
            stream = StringIO(response.read())
            result = gzip.GzipFile(fileobj=stream)
        else:
            result = response

        return ET.parse(result).getroot()
        #return ET.parse(result)

    def _parse_feed(self, dom):
        items = []
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

            items.append(item)

        return items

    def get_torrents(self):
        torrents_keys = self.torrents.keys()

        print "Downloading list..."
        dom = self._download_feed(self.FEED_URL)
        print "Parsing..."
        items = self._parse_feed(dom)
        total_items = len(items)
        i = 1
        for item in items:
            print "Processing %d/%d..." % (i, total_items)
            i += 1

            if item['title'] in torrents_keys:
                print "Already cached." + item['title']
                continue

            torrent = {'show_id': None,
                       'show_title': None,
                       'show_episode': None,
                       'show_group': None,
                       'status': self.STATUS_NOT_FOUND,
                      }

            highest_ratio = (None, 0)
            aie = extras.AnimeInfoExtractor.AnimeInfoExtractor(item['title'])
            (item_title, item_episode, item_group) = (aie.getName(), aie.getEpisode(), aie.subberTag)

            torrent['show_title'] = item_title
            torrent['show_episode'] = item_episode
            torrent['show_group'] = item_group

            if not item_title:
                #print "Not recognized: %s\n  %s" % (item['title'], repr(anal))
                torrent['status'] = self.STATUS_NOT_RECOGNIZED
                continue

            show = utils.guess_show(item_title, self.animelist)

            if show:
                torrent['show_id'] = show['id']
                #torrent['show_title'] = show['title']

                if item_episode == (show['my_progress'] + 1):
                    # Show found!
                    torrent['status'] = self.STATUS_NEXT_EPISODE
                elif item_episode > (show['my_progress'] + 1):
                    torrent['status'] = self.STATUS_NOT_NEXT_EPISODE
                else:
                    # The show was found but this episode was already watched
                    torrent['status'] = self.STATUS_WATCHED
            else:
                # This show isn't in the list
                print "Not found: %s" % (item['title'])
                pass

            # Add to the list
            self.torrents[item['title']] = torrent

        self._save()
        print "Done!"
        return self.torrents

    def get_sorted_torrents(self):
        from operator import itemgetter
        d = self.get_torrents().values()
        return sorted(d, key=itemgetter('status'))

