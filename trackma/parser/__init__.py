def get_parser_class(msg, parser_name):
    # Choose the parser we want to use
    if parser_name == 'aie':
        msg.debug('Using AnimeInfoExtractor parser')
        from .animeinfoextractor import AnimeInfoExtractor
        return AnimeInfoExtractor
    elif parser_name == 'anitopy':
        msg.debug('Using Anitopy parser')
        from .anitopy import AnitopyWrapper
        return AnitopyWrapper
    else:
        msg.debug('Unknown parser "{}", falling back to default'.format(parser_name))
        return get_parser_class('aie')
