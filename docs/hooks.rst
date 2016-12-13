Introduction
============
Trackma now includes a multi-hook (pseudo-plugin) system for extended functionality.
This can include calling an external program or service (like Twitter) or doing other calculations or changes to the database.

A hook file gets called every time Trackma's engine emits a signal; this is whether an episode is playing,
a show has been added, updated, deleted or synced, the tracker has detected a file, etc.
In general any signal emitted by the engine can be hooked (see the signals dict in engine.py for all the available signals).

Using hook files
================
To use a hook file it's as simple as copying it inside the **~/.trackma/hooks** directory (create it if doesn't exist).
It will get automatically loaded by Trackma the next time it starts.

Creating a hook file
====================
A hook file is a normal Python file. To create a function that hooks a signal, you must create a def with the same name and parameters as the hook.
For example, if you want to hook the show_added signal::

    def show_added(engine, show):
        print("The show", show['title'], "was added!")

As you can see, in this signal the engine object is passed, as well as the added show dictionary.
There's also an optional special init function that gets called when Trackma loads the hook::

    def init(engine):
        # Initialization here...

You can also use the engine messenger directly to show messages to the user::

    engine.msg.info('my_hook', 'Example message.')

For a full example template to build your hook on, please see the hooks/example.py file.
