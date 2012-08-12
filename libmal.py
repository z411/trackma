import urllib2
import xml.etree.ElementTree as ET

class libmal:
    """
    API class to communicate with MyAnimeList
    Should inherit a base library interface.
    """
    name = 'libmal'
    
    username = '' # TODO Must be filled by check_credentials
    password_mgr = None
    handler = None
    opener = None
    msg = None
    
    def __init__(self, messenger, username, password):
        """Initializes the useragent through credentials."""
        self.msg = messenger
        self.username = username
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("MyAnimeList API", "myanimelist.net:80", username, password);
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)
        urllib2.install_opener(self.opener)
        
        self.msg.info(self.name, 'Version v0.1')
    
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        self.msg.info(self.name, 'Logging in...')
        try:
            response = self.opener.open("http://myanimelist.net/api/account/verify_credentials.xml")
            return True
        except urllib2.HTTPError, e:
            self.msg.error(self.name, 'Incorrect credentials.')
            return False
    
    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.msg.info(self.name, 'Downloading anime list...')
        
        showlist = dict()
        try:
            response = self.opener.open("http://myanimelist.net/malappinfo.php?u="+self.username+"&status=all&type=anime")
            data = response.read()
            
            root = ET.fromstring(data)
            
            self.msg.info(self.name, 'Parsing list...')
            
            # Load data into a parsed dictionary
            for child in root:
                if child.tag == 'anime':
                    show_id = int(child.find('series_animedb_id').text)
                    
                    showlist[show_id] = {
                        'id':           show_id,
                        'title':        child.find('series_title').text.encode('utf-8'),
                        'my_episodes':  int(child.find('my_watched_episodes').text),
                        'my_status':    int(child.find('my_status').text),
                        'episodes':     int(child.find('series_episodes').text),
                        'status':       int(child.find('series_status').text),
                    }
            
            return showlist
        except urllib2.HTTPError, e:
            self.msg.error(self.name, 'Error getting list.')
            return False
    
