Developer Documentation
***********************

Trackma's design has four main elements:

1. User Interface (Only has to worry about talking to the Engine)
2. Engine (Trackma's core)
3. Data Handler
4. Library/API (Network communication occurs here)

Communications occur from top to bottom, and then responses travel botom to top.

Engine
======

.. automodule:: trackma.engine
   :members:

Account Manager
===============

.. automodule:: trackma.accounts
   :members:

Library Interface
=================

.. automodule:: trackma.lib.lib
   :members:
