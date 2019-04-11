from trackma import utils

NAME = "My test Trackma plugin"

class ApiPlugin():
    NAME = "My api"
    SHORTNAME = "yea"
    ICON = utils.datadir + '/data/kitsu.png'
    LOGIN = utils.LOGIN_PASSWD

    def init(messenger, account, userconfig):
        from . import api

        return api.Api(messenger, account, userconfig)

class HooksPlugin():
    def init(engine):
        from . import hooks

        return hooks.Hooks(engine)
