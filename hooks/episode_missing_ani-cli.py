"""
 Author: imsamuka
 Place under ~/.config/trackma/hooks/ or ~/.trackma/hooks/

 When an episode is not found, it executes 'ani-cli' to find and
 watch it via streaming automatically!
"""

import shutil
from trackma import utils


# Executed when trying to watch an episode that doesn't exist in your library
def episode_missing(engine, show, episode):

    query = show["title"].strip()
    anicli = shutil.which("ani-cli")  # find 'ani-cli' executable
    if anicli:
        args = [anicli, "-q", "best", "-e", str(episode), query]
        cmd = " ".join(args[:-1]) + f" '{query}'"
        engine.msg.info("episode_missing", cmd)  # Show the command used
        utils.spawn_process(args)
    else:
        engine.msg.info("episode_missing", "ani-cli was not found")
