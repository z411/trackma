from trackma import utils
from trackma.extras import AnimeInfoExtractor

import pickle
import urllib.request
import xml.etree.ElementTree as ET
import gzip
from io import StringIO

class RSS(object):
    results = {}
    name = 'RSS'

    def __init__(self, messenger, showlist, config):
        self.msg = messenger
        self.showlist = showlist
        self.config = config

        utils.make_dir(utils.to_cache_path())
        self.filename = utils.to_cache_path('rss.cache')
        self._load()

    def _load(self):
        if utils.file_exists(self.filename):
            try:
                with open(self.filename, 'rb') as f:
                    self.results = pickle.load(f)
            except:
                pass

    def _save(self):
        with open(self.filename, 'wb') as f:
            pickle.dump(self.results, f)

    def _download_feed(self, url):
        req = urllib.request.Request(url)
        req.add_header('Accept-Encoding', 'gzip')
        response = urllib.request.urlopen(req)

        if response.info().get('content-encoding') == 'gzip':
            #stream = StringIO(response.read())
            stream = response
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

    def get_results(self, refresh):
        if not refresh and self.results:
            return self.results

        self.msg.info(self.name, "Downloading RSS feed...")
        dom = self._download_feed(self.config['rss_url'])
        self.msg.info(self.name, "Parsing results...")
        items = self._parse_feed(dom)

        for item in items:
            aie = AnimeInfoExtractor(item['title'])

            result = {
                       'filename': item['title'],
                       'url': item['link'],
                       'show_title': aie.getName(),
                       'episode': aie.getEpisode(),
                       'group': aie.subberTag,
                       'resolution': aie.resolution,
                       'description': item['description'],
                       'date': item.get('pubDate'),
                       'status': utils.RSS_NOT_FOUND,
                       'marked': False,
                      }

            if not result['show_title']:
                result['status'] = utils.RSS_NOT_RECOGNIZED
                continue

            show = utils.guess_show(result['show_title'], self.showlist)

            if show:
                result['show_id'] = show['id']
                result['show_title'] = show['title']

                if result['episode'] == (show['my_progress'] + 1):
                    # Show found!
                    result['status'] = utils.RSS_NEXT_EPISODE
                elif result['episode'] > (show['my_progress'] + 1):
                    result['status'] = utils.RSS_NOT_NEXT_EPISODE
                else:
                    # The show was found but this episode was already watched
                    result['status'] = utils.RSS_WATCHED
            else:
                # This show isn't in the list
                pass

            if result['status'] < utils.RSS_WATCHED:
                result['marked'] = True

            # Add to the list
            self.results[item['title']] = result

        self._save()
        return self.results

    def get_sorted_results(self, refresh):
        from operator import itemgetter
        d = self.get_results(refresh).values()
        return sorted(d, key=itemgetter('status'))

    def download(method, items):
        for item in items:
            print("Getting {}".format(item['url']))

