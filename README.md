# AnICA UI

This is the web user interface for AnICA ("Analyzing Inconsistencies in Microarchitectural Code Analyzers").
Its purpose is to visualize the results of AnICA's inconsistency discovery campaigns and generalizations for single discoveries.
Configuring and running new campaigns or generalizations is (currently) not supported by this UI and needs to be done with AnICA's configuration files and command line interface directly (it can be found as a submodule in `lib/anica`, check the README there for more details).

The UI is implemented as a webapp in [django](https://www.djangoproject.com/).
At the current point, it is only intended and optimized for local use on the same machine, a machine in a restricted local network, or from inside a virtual machine.
**Use on a public-facing web server is not recommended** since the implementation is rather backend-heavy and might enable denial of service attacks.

The UI has only been tested on Linux systems.


## Installation

### Development Version

Make sure that you have `llvm-mc` on your path (most likely by installing [LLVM](https://llvm.org/)).
It is used by the iwho subcomponent (at `lib/anica/lib/iwho`) to handle basic instruction (dis)assembly tasks.
Furthermore, you need a python3 setup with the `venv` standard module available.

Run the `./setup_venv.sh` script to set up a virtual environment for the AnICA UI at `./env/anica_ui`.
Whenever you run any of the AnICA UI commands below in a shell, you will need to have activated the virtual environment with `source ./env/anica_ui/bin/activate`.
This virtual environment is a suitable replacement the one in the AnICA project.
This means that you can use it to run all commands belonging to the AnICA and IWHo subprojects.


## Usage

### Running the UI
With activated virtual environment, the django test server is started using the following command:
```
./manage.py runserver 8000
```
While this command is running on a system, the UI will be available on that system
in a web browser (tested mainly with Chromium) at
`http://127.0.0.1:8000/anica/`.

All pages of the UI have a "Help" button in the top-right corner that opens a side pane with information about the current page.

### Adding New Campaigns

In a first step, post-process the AnICA results with the following command to add additional metrics for the UI:
```
./tools/add_metrics.py path/to/first/campaign/dir path/to/second/campaign/dir ...
```
The passed paths should be results of AnICA's discovery campaigns (as produced by `anica-discover`; among other things, there should be a `campaign_config.json`) directly in this directory.


New AnICA campaigns can be added to the UI via a [management command](https://docs.djangoproject.com/en/3.2/howto/custom-management-commands/):
```
./anica_ui/manage.py import_campaigns <TAG> path/to/first/campaign/dir path/to/second/campaign/dir ...
```

The first `<TAG>` argument is an identifier that is in the UI to organize campaigns.
Campaigns can be filtered and sorted according to their tag.


### Adding New Generalizations

Generalizations (as produced by `anica-generalize`) do not require preprocessing and are imported in a similar fashion:

```
./anica_ui/manage.py import_generalization path/to/generalization/dir
```

### Flushing the UI

You can clear all campaigns and generalizations from the UI by flushing its database:
```
./anica_ui/manage.py flush
```
This does not affect the campaign directories (and does not undo the post-processing via the `add_metrics.py` script).


### For Developers Only: Updating the Database

If the code of the webapp is adjusted (specifically, if the datamodel in `anica_ui/basic_ui/models.py` is changed), the data base of the webapp needs to be updated using.
```
./anica_ui/manage.py makemigrations
./anica_ui/manage.py migrate
```
If necessary, there will be a query for specifying default values for newly added fields.


