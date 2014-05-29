2sync
=====

A command-line tool for 2 way synchronisation on Linux

WARNING: This tool is at the moment just an development version. Don't use it productive

It's a simple tool to do 2 way synchronisation local an remote (ssh).
It check files from 2 two paths and synchronise it.

I found a few other tools who do this, but it doesn't match my needs. So I started to develop a tool.
Maybe you like the other tool. Have a look at unison and/or git-annex

Depends: python (>= 3.4.0) , PyGObject (aka PyGI), paramiko (>= 1.3)

2sync.py -h for help

ToDo:
===
Functional:
- Better ErrorHandling and logging
- Support for "paths" in config
- Support for Backups (secure overwriting files and create backups)
- Restore for Backups
- Support for batch and auto mode
- Exit states

GUI:
- Shortcuts
- Config file editable over GUI

Other:
- Create tutorials, how to's, examples