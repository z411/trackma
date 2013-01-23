import utils
import cPickle

class AccountManager(object):
    accountfile = utils.get_root_filename('accounts')
    accounts = {'default': None, 'accounts': []}
    filename = 'accounts'

    def __init__(self):
        utils.make_dir('')
        self.filename = utils.get_root_filename('accounts')
        self._load()

    def _load(self):
        if utils.file_exists(self.filename):
            print self.filename
            with open(self.filename, 'rb') as f:
                self.accounts = cPickle.load(f)

    def _save(self):
        with open(self.filename, 'wb') as f:
            cPickle.dump(self.accounts, f)
            f.write('ok')

    def add_account(self, username, password, api):
        account = {'username': username,
                   'password': password,
                   'api': api,
                  }
        self.accounts['accounts'].append(account)
        self._save()
    
    def delete_account(self, num):
        self.accounts['accounts'].pop(num)
        self._save()
    
    def get_account(self, num):
        return self.accounts['accounts'][num]
    
    def get_accounts(self):
        return self.accounts['accounts']

    def get_default(self):
        num = self.accounts['default']
        if num is not None:
            return self.accounts['accounts'][num]
        else:
            return None

    def set_default(self, val):
        self.accounts['default'] = val
        self._save()

    def unset_default(self):
        self.accounts['default'] = None


