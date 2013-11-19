import utils
import cPickle

class AccountManager(object):
    accounts = {'default': None, 'next': 1, 'accounts': dict()}

    def __init__(self):
        utils.make_dir('')
        self.filename = utils.get_root_filename('accounts.dict')
        self._load()

    def _load(self):
        if utils.file_exists(self.filename):
            with open(self.filename, 'rb') as f:
                self.accounts = cPickle.load(f)

    def _save(self):
        with open(self.filename, 'wb') as f:
            cPickle.dump(self.accounts, f)

    def add_account(self, username, password, api, extra={}):
        available_libs = utils.available_libs.keys()
        
        if api not in available_libs:
            raise utils.AccountError('That API doesn\'t exist.')

        account = {'username': username,
                   'password': password,
                   'api': api,
                  }
                  
        if extra != {}:
	        account.update(extra)

        nextnum = self.accounts['next']
        self.accounts['accounts'][nextnum] = account
        self.accounts['next'] += 1
        self._save()
    
    def delete_account(self, num):
        self.accounts['default'] = None
        del self.accounts['accounts'][num]
        self._save()
    
    def get_account(self, num):
        return self.accounts['accounts'][num]
    
    def get_accounts(self):
        return self.accounts['accounts'].iteritems()

    def get_default(self):
        num = self.accounts['default']
        if num is not None:
            try:
                return self.accounts['accounts'][num]
            except KeyError:
                return None
        else:
            return None

    def set_default(self, val):
        self.accounts['default'] = val
        self._save()

    def unset_default(self):
        self.accounts['default'] = None


