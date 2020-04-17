import pickle
from trackma import utils

class AccountManager:
    """
    This is the account manager.

    It provides a generic way for the user interface to query for the
    available registered accounts, and add or delete accounts.

    This class returns an Account Dictionary used by
    the :class:`Engine` to start.
    """
    accounts = {'default': None, 'next': 1, 'accounts': dict()}

    def __init__(self):
        utils.make_dir(utils.to_config_path())
        self.filename = utils.to_config_path('accounts.dict')
        self._load()

    def _load(self):
        if utils.file_exists(self.filename):
            with open(self.filename, 'rb') as f:
                self.accounts = pickle.load(f)

    def _save(self):
        is_new = not utils.file_exists(self.filename)
        with open(self.filename, 'wb') as f:
            if is_new:
                utils.change_permissions(self.filename, 0o600)
            pickle.dump(self.accounts, f, protocol=2)

    def add_account(self, username, password, api):
        """
        Registers a new account with the specified
        *username*, *password*, and *api*.

        The *api* must be one of the available APIs
        found in the utils.available_libs dict.
        """

        available_libs = utils.available_libs.keys()

        if not username:
            raise utils.AccountError('Empty username.')
        if not password:
            raise utils.AccountError('Empty password.')
        if api not in available_libs:
            raise utils.AccountError('That API doesn\'t exist.')

        account = {'username': username,
                   'password': password,
                   'api': api,
                  }

        nextnum = self.accounts['next']
        self.accounts['accounts'][nextnum] = account
        self.accounts['next'] += 1
        self._save()

    def edit_account(self, num, username, password, api):
        """
        Updates data for account *num* with the specified
        *username*, *password*, and *api*.
        """

        available_libs = utils.available_libs.keys()

        if not username:
            raise utils.AccountError('Empty username.')
        if not password:
            raise utils.AccountError('Empty password.')
        if api not in available_libs:
            raise utils.AccountError('That API doesn\'t exist.')

        account = {'username': username,
                   'password': password,
                   'api': api,
                  }

        self.accounts['accounts'][num].update(account)
        self._save()

    def delete_account(self, num):
        """
        Deletes the account number **num**.
        """
        self.accounts['default'] = None
        del self.accounts['accounts'][num]

        # Reset index if there are no accounts left
        if not self.accounts['accounts']:
            self.accounts['next'] = 1

        self._save()

    def purge_account(self, num):
        """
        Renames stale cache files for account number **num**.
        """
        account = self.accounts['accounts'][num]
        userfolder = utils.to_data_path("%s.%s" % (account['username'], account['api']))
        utils.make_dir(userfolder + '.old')
        utils.regex_rename_files('(.*.queue)|(.*.info)|(.*.list)|(.*.meta)', userfolder, userfolder + '.old')

    def get_account(self, num):
        """
        Returns the account dict **num**.
        """
        return self.accounts['accounts'][num]

    def get_accounts(self):
        """
        Returns an iterator of available accounts.
        """
        return self.accounts['accounts'].items()

    def get_default(self):
        """
        Returns the default account number, if set.
        Otherwise returns None.
        """
        num = self.accounts['default']
        if num is not None:
            try:
                return self.accounts['accounts'][num]
            except KeyError:
                return None
        else:
            return None

    def set_default(self, val):
        """
        Sets a new default account number.
        """
        self.accounts['default'] = val
        self._save()

    def unset_default(self):
        """
        Unsets the default account number.
        """
        self.accounts['default'] = None
