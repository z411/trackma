COMMENT_CHAR = '#'
OPTION_CHAR =  '='
 
def parse_config(filename):
    options = {}
    f = open(filename)
    for line in f:
        # Remove comments
        if COMMENT_CHAR in line:
            line, comment = line.split(COMMENT_CHAR, 1)
        # Store options
        if OPTION_CHAR in line:
            option, value = line.split(OPTION_CHAR, 1)
            option = option.strip()
            value = value.strip()
            options[option] = value
    f.close()
    return options
