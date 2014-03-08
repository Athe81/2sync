2sync
=====

NEW: Ported to Python 3

A command-line tool for 2 way synchronisation

WARNING: This tool is at the moment just an development version. Don't use it productive

It's a simple tool to do 2 way synchronisation on filesystem.
It check files from 2 two paths and synchronise it.

I found a few other tools who do this, but it doesn't match my needs. So I started to develop a tool.
Maybe you like the other tool. Have a look at unison and/or git-annex

Depends: python3

<!--
Usage:
```
2sync [OPTION] NAME
OPTION:
	--create	create a new config
	--delete	delete a existing config
```
-->

ToDo:
===
- Add ErrorHandling
- Add expanded inspection on conflicts
- Add support for paths in config
- Add support for remote paths over ssh
- Create backups before files deleted or overwritten
- Add command-line options
