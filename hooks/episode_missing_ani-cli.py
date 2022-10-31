"""
 Author: imsamuka
 Place under ~/.config/trackma/hooks/ or ~/.trackma/hooks/

 When an episode is not found, it executes 'ani-cli' to find and
 watch it via streaming automatically!
"""

import shutil
from subprocess import Popen, PIPE, DEVNULL 


# Executed when trying to watch an episode that doesn't exist in your library
def episode_missing(engine, show, episode):
    anicli = shutil.which("ani-cli")  # find 'ani-cli' executable
    if anicli:
        query = show["title"].strip()
        args = [anicli, "-q", "best", "-a", str(episode), query]
        cmd = " ".join(args[:-1]) + f" '{query}'"
        engine.msg.info("episode_missing", cmd)  # Show the command used
        process = Popen(args, stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL, text=True)
        process.communicate(input="q")
    else:
        engine.msg.info("episode_missing", "ani-cli was not found")

# You can run this file directly to test it
if __name__ == "__main__":
    class MockEngine:
        class Messenger:
            info = print
        msg = Messenger()
    episode_missing(MockEngine(), {"title": "Jiandao Di Yi Xian"}, 9)
