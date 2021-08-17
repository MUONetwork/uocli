=====
uocli
=====

  This is a heavily work in progress repo.


.. image:: https://img.shields.io/pypi/v/uocli.svg
        :target: https://pypi.python.org/pypi/uocli

.. image:: https://img.shields.io/travis/mohitsharma44/uocli.svg
        :target: https://travis-ci.com/mohitsharma44/uocli

.. image:: https://readthedocs.org/projects/uocli/badge/?version=latest
        :target: https://uocli.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status




CLI for interacting with MUON computational facility

Installation
------------
* Using pip::
.. code-block:: bash

  pip install -e git+https://github.com/MUONetwork/uocli.git

* Using pipx_::
.. code-block:: bash

  pipx install git+https://github.com/MUONetwork/uocli.git

.. _pipx: https://github.com/pypa/pipx

How to use
----------
* You can find help for all supported commands/subcommands by passing ``--help`` to ``uocli <command/subcommand>``

.. code-block:: bash

  $ uocli --help
  Usage: uocli [OPTIONS] COMMAND [ARGS]...

  Commandline interface to interact with the UO backend infrastructure

  Options:
    --version  Show the version and exit.
    --help     Show this message and exit.

  Commands:
    jupyterhub  Connect to Jupyterhub
    storage     Handle Storage related operations
    vm          Handle VM related operations

* To create new VM with ubuntu 2004 xfce desktop template::
.. code-block:: bash

  $ uocli vm new --help
  $ uocli vm new --vmname testfrommac --template ubuntu-2004-xfce-template --storage luna --sshkey ~/.ssh/id_rsa.pub

* To list all your VMs::

.. code-block:: bash

  $ uocli vm list

* To connect to your VM over spiceproxy::
.. code-block:: bash

  $ uocli vm connect --vmid 110 --spice

.. include:: CONTRIBUTING.rst

License and Docs
----------------

* Free software: MIT license
* (WIP)Documentation: https://uocli.readthedocs.io.
